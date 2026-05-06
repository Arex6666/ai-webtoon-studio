"""SkillLoader — scans builtin/ at startup, loads installed skills from DB."""
import importlib.util
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.agent.skills.manifest import parse_manifest, ManifestError, SkillManifest, validate_external_safety
from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY
from app.models.skill_installation import SkillInstallation

logger = logging.getLogger(__name__)


# apps/api/app/services/agent/skills/loader.py → apps/api/skills/
BUILTIN_SKILLS_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "skills"


class LoadedSkill:
    def __init__(self, install_id: str, manifest: SkillManifest, root: Path):
        self.install_id = install_id
        self.manifest = manifest
        self.root = root
        self.registered_tool_names: list[str] = []
        self.guidance_text: Optional[str] = None


_loaded: dict[str, LoadedSkill] = {}    # install_id → LoadedSkill


def get_loaded(install_id: str) -> Optional[LoadedSkill]:
    return _loaded.get(install_id)


def list_loaded() -> list[LoadedSkill]:
    return list(_loaded.values())


def bootstrap(db: Session) -> None:
    """Run at API startup: scan builtin/, then load active SkillInstallation rows."""
    _load_builtin_skills(db)
    _load_installed_skills(db)


def _load_builtin_skills(db: Session) -> None:
    if not BUILTIN_SKILLS_DIR.exists():
        logger.info("No builtin skills directory at %s — skipping", BUILTIN_SKILLS_DIR)
        return
    for sub in sorted(BUILTIN_SKILLS_DIR.iterdir()):
        if not sub.is_dir() or not (sub / "skill.yaml").exists():
            continue
        try:
            manifest = parse_manifest(sub)
            install = _upsert_builtin_install(db, manifest, sub)
            _load_skill_into_registry(install.id, manifest, sub, is_builtin=True)
        except (ManifestError, Exception) as e:
            logger.exception("Failed to load builtin skill at %s: %s", sub, e)


def _upsert_builtin_install(db: Session, manifest: SkillManifest, root: Path) -> SkillInstallation:
    existing = db.query(SkillInstallation).filter(
        SkillInstallation.name == manifest.name,
        SkillInstallation.scope == "global",
        SkillInstallation.project_id.is_(None),
        SkillInstallation.source_type == "builtin",
    ).first()
    if existing:
        existing.version = manifest.version
        existing.manifest_json = _manifest_to_json(manifest)
        existing.install_path = str(root)
        existing.last_loaded_at = datetime.utcnow()
        existing.status = "active"
        db.commit()
        return existing
    inst = SkillInstallation(
        name=manifest.name, version=manifest.version,
        source_type="builtin", source_url=None, install_path=str(root),
        manifest_json=_manifest_to_json(manifest),
        status="active", scope="global", project_id=None,
        installed_at=datetime.utcnow(), last_loaded_at=datetime.utcnow(),
    )
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst


def _load_installed_skills(db: Session) -> None:
    rows = db.query(SkillInstallation).filter(
        SkillInstallation.status == "active",
        SkillInstallation.source_type != "builtin",
    ).all()
    for row in rows:
        try:
            root = Path(row.install_path) if row.install_path else None
            if not root or not root.exists():
                row.status = "failed"
                row.failure_reason = f"install path missing: {row.install_path}"
                db.commit()
                continue
            manifest = parse_manifest(root)
            if row.source_type != "builtin":
                validate_external_safety(manifest)
            _load_skill_into_registry(row.id, manifest, root, is_builtin=False)
            row.last_loaded_at = datetime.utcnow()
            db.commit()
        except Exception as e:
            logger.exception("Failed to load installed skill %s: %s", row.name, e)
            row.status = "failed"
            row.failure_reason = str(e)
            db.commit()


def _load_skill_into_registry(install_id: str, manifest: SkillManifest, root: Path, is_builtin: bool) -> None:
    loaded = LoadedSkill(install_id=install_id, manifest=manifest, root=root)
    if manifest.guidance:
        guidance_path = root / manifest.guidance.file
        if guidance_path.exists():
            loaded.guidance_text = guidance_path.read_text(encoding="utf-8")
    if is_builtin and manifest.tools:
        for ts in manifest.tools:
            tool = _import_tool_handler(root, ts, install_id, is_builtin)
            if tool:
                TOOL_REGISTRY.register(tool)
                loaded.registered_tool_names.append(tool.name)
    # MCP server start handled by mcp_client_pool (later batch)
    _loaded[install_id] = loaded


def _import_tool_handler(root: Path, ts, install_id: str, is_builtin: bool) -> Optional[ToolDefinition]:
    """Import a builtin skill's bundled tool handler from a relative module path.

    handler format: "module.path:function_name" (relative to skill root).
    """
    try:
        module_part, func_part = ts.handler.split(":", 1)
        module_path = root / (module_part.replace(".", "/") + ".py")
        spec = importlib.util.spec_from_file_location(f"skill_{install_id}_{module_part}", module_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        handler = getattr(mod, func_part)
        return ToolDefinition(
            name=ts.name, description=ts.schema.get("description", ts.name),
            json_schema=ts.schema, handler=handler,
            requires_context=tuple(),
            expected_duration=ts.expected_duration, read_only=ts.read_only,
            source_skill_id=install_id,
        )
    except Exception as e:
        logger.exception("Failed to import tool handler %s from skill %s: %s", ts.handler, install_id, e)
        return None


def unload_skill(install_id: str) -> None:
    """Remove a skill's tools from the registry; called by lifecycle on disable/uninstall."""
    loaded = _loaded.pop(install_id, None)
    if not loaded:
        return
    for name in loaded.registered_tool_names:
        TOOL_REGISTRY.deregister(name)


def _manifest_to_json(m: SkillManifest) -> dict:
    """Serialize manifest dataclass to JSON-safe dict for DB storage."""
    return {
        "name": m.name, "version": m.version, "description": m.description,
        "author": m.author, "license": m.license, "homepage": m.homepage,
        "activation": {
            "intent_keywords": list(m.activation.intent_keywords),
            "context_required": list(m.activation.context_required),
            "context_optional": list(m.activation.context_optional),
        },
        "scope_default": m.scope_default,
        "has_guidance": m.guidance is not None,
        "has_mcp_server": m.mcp_server is not None,
        "has_tools": m.has_tools_bundled(),
    }
