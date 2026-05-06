"""SkillInstaller — fetch source → validate → move to install path → load."""
import os
import shutil
import tempfile
import tarfile
import zipfile
import urllib.request
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.agent.skills.manifest import parse_manifest, validate_external_safety, ManifestError
from app.services.agent.skills.loader import _load_skill_into_registry
from app.models.skill_installation import SkillInstallation

logger = logging.getLogger(__name__)


def install_local(db: Session, source_path: str, scope: str = "project", project_id: Optional[str] = None) -> SkillInstallation:
    src = Path(source_path).expanduser().resolve()
    if not src.is_dir():
        raise ValueError(f"Local install requires a directory; got {src}")
    return _do_install(db, src, source_type="local", source_url=str(src), scope=scope, project_id=project_id)


def install_url(db: Session, url: str, scope: str = "project", project_id: Optional[str] = None) -> SkillInstallation:
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError("URL install requires http(s):// scheme")
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "skill_archive"
        urllib.request.urlretrieve(url, archive)
        extract_dir = Path(tmp) / "extracted"
        extract_dir.mkdir()
        if tarfile.is_tarfile(archive):
            with tarfile.open(archive) as tf:
                tf.extractall(extract_dir)
        elif zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(extract_dir)
        else:
            raise ValueError("URL must point to a .tar.gz or .zip archive")
        src = _find_skill_root(extract_dir)
        return _do_install(db, src, source_type="url", source_url=url, scope=scope, project_id=project_id)


def install_git(db: Session, git_url: str, scope: str = "project", project_id: Optional[str] = None) -> SkillInstallation:
    """git_url format: git+https://host/owner/repo[@ref][#path=subdir]"""
    if not git_url.startswith("git+"):
        raise ValueError("Git URL must start with git+")
    bare = git_url[len("git+"):]
    subpath = ""
    ref = None
    if "#path=" in bare:
        bare, subpath = bare.split("#path=", 1)
    if "@" in bare and bare.rfind("@") > bare.find("://") + 3:
        bare, ref = bare.rsplit("@", 1)
    with tempfile.TemporaryDirectory() as tmp:
        clone_dir = Path(tmp) / "repo"
        from git import Repo
        if ref:
            Repo.clone_from(bare, clone_dir, depth=1, branch=ref)
        else:
            Repo.clone_from(bare, clone_dir, depth=1)
        skill_root = clone_dir / subpath if subpath else clone_dir
        src = _find_skill_root(skill_root)
        return _do_install(db, src, source_type="git", source_url=git_url, scope=scope, project_id=project_id)


def _find_skill_root(start: Path) -> Path:
    """Locate skill.yaml within `start` (up to depth 2)."""
    if (start / "skill.yaml").exists():
        return start
    for sub in start.iterdir():
        if sub.is_dir() and (sub / "skill.yaml").exists():
            return sub
    raise ManifestError(f"No skill.yaml found within {start}")


def _do_install(
    db: Session, src: Path, *, source_type: str, source_url: str,
    scope: str, project_id: Optional[str],
) -> SkillInstallation:
    manifest = parse_manifest(src)
    validate_external_safety(manifest)

    data_dir = Path(os.path.expanduser(settings.WEBTOON_DATA_DIR))
    if scope == "global":
        target = data_dir / "skills" / "global" / f"{manifest.name}-{manifest.version}"
    else:
        if not project_id:
            raise ValueError("scope='project' requires project_id")
        target = data_dir / "skills" / "projects" / project_id / f"{manifest.name}-{manifest.version}"

    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, target)

    inst = SkillInstallation(
        name=manifest.name, version=manifest.version,
        source_type=source_type, source_url=source_url,
        install_path=str(target), manifest_json=_manifest_dict(manifest),
        status="active", scope=scope, project_id=project_id,
        installed_at=datetime.utcnow(), last_loaded_at=datetime.utcnow(),
    )
    db.add(inst)
    db.commit()
    db.refresh(inst)

    _load_skill_into_registry(inst.id, manifest, target, is_builtin=False)
    return inst


def _manifest_dict(m) -> dict:
    return {
        "name": m.name, "version": m.version, "description": m.description,
        "author": m.author, "scope_default": m.scope_default,
        "has_guidance": m.guidance is not None, "has_mcp_server": m.mcp_server is not None,
    }
