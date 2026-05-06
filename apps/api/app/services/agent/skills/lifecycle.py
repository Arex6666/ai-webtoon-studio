"""Enable / disable / uninstall actions on installed skills."""
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.skill_installation import SkillInstallation
from app.services.agent.skills.loader import unload_skill, _load_skill_into_registry
from app.services.agent.skills.manifest import parse_manifest, validate_external_safety


def disable(db: Session, install_id: str) -> SkillInstallation:
    inst = db.query(SkillInstallation).filter_by(id=install_id).one()
    if inst.status == "disabled":
        return inst
    unload_skill(install_id)
    inst.status = "disabled"
    db.commit()
    return inst


def enable(db: Session, install_id: str) -> SkillInstallation:
    inst = db.query(SkillInstallation).filter_by(id=install_id).one()
    if inst.status == "active":
        return inst
    if not inst.install_path:
        raise ValueError(f"Skill {inst.name} has no install_path; cannot enable")
    root = Path(inst.install_path)
    if not root.exists():
        raise ValueError(f"Install path missing: {inst.install_path}")
    manifest = parse_manifest(root)
    if inst.source_type != "builtin":
        validate_external_safety(manifest)
    _load_skill_into_registry(install_id, manifest, root, is_builtin=(inst.source_type == "builtin"))
    inst.status = "active"
    inst.last_loaded_at = datetime.utcnow()
    db.commit()
    return inst


def uninstall(db: Session, install_id: str) -> None:
    inst = db.query(SkillInstallation).filter_by(id=install_id).one()
    unload_skill(install_id)
    if inst.install_path and inst.source_type != "builtin":
        try:
            shutil.rmtree(inst.install_path)
        except FileNotFoundError:
            pass
    inst.status = "uninstalled"
    db.commit()
