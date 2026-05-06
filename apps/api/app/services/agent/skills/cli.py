"""webtoon-skill CLI — thin REST wrapper for skill management.

Run via: py -3.13 -m app.services.agent.skills.cli <command> [args]
"""
import argparse
import sys
from pathlib import Path

from app.db.database import SessionLocal
from app.services.agent.skills import installer, lifecycle
from app.models.skill_installation import SkillInstallation


def cmd_list(args):
    db = SessionLocal()
    rows = db.query(SkillInstallation).all()
    for r in rows:
        print(f"{r.name}@{r.version}  status={r.status}  scope={r.scope}  source={r.source_type}  id={r.id}")


def cmd_install(args):
    db = SessionLocal()
    if args.source.startswith(("http://", "https://")):
        inst = installer.install_url(db, args.source, scope=args.scope, project_id=args.project_id)
    elif args.source.startswith("git+"):
        inst = installer.install_git(db, args.source, scope=args.scope, project_id=args.project_id)
    else:
        inst = installer.install_local(db, args.source, scope=args.scope, project_id=args.project_id)
    print(f"installed: {inst.name}@{inst.version} id={inst.id}")


def cmd_disable(args):
    db = SessionLocal()
    inst = db.query(SkillInstallation).filter_by(name=args.name, status="active").first()
    if not inst:
        print(f"no active skill named {args.name}", file=sys.stderr)
        sys.exit(1)
    lifecycle.disable(db, inst.id)
    print(f"disabled: {inst.name}")


def cmd_enable(args):
    db = SessionLocal()
    inst = db.query(SkillInstallation).filter_by(name=args.name).order_by(SkillInstallation.installed_at.desc()).first()
    if not inst:
        print(f"no skill named {args.name}", file=sys.stderr)
        sys.exit(1)
    lifecycle.enable(db, inst.id)
    print(f"enabled: {inst.name}")


def cmd_uninstall(args):
    db = SessionLocal()
    inst = db.query(SkillInstallation).filter_by(name=args.name).first()
    if not inst:
        print(f"no skill named {args.name}", file=sys.stderr)
        sys.exit(1)
    lifecycle.uninstall(db, inst.id)
    print(f"uninstalled: {inst.name}")


def cmd_validate(args):
    from app.services.agent.skills.manifest import parse_manifest, validate_external_safety
    m = parse_manifest(Path(args.path))
    validate_external_safety(m)
    print(f"OK: {m.name}@{m.version}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="webtoon-skill")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list").set_defaults(func=cmd_list)

    pi = sub.add_parser("install")
    pi.add_argument("source", help="Path, URL, or git+ URL")
    pi.add_argument("--scope", choices=["global", "project"], default="project")
    pi.add_argument("--project-id", default=None)
    pi.set_defaults(func=cmd_install)

    pd = sub.add_parser("disable")
    pd.add_argument("name")
    pd.set_defaults(func=cmd_disable)

    pe = sub.add_parser("enable")
    pe.add_argument("name")
    pe.set_defaults(func=cmd_enable)

    pu = sub.add_parser("uninstall")
    pu.add_argument("name")
    pu.set_defaults(func=cmd_uninstall)

    pv = sub.add_parser("validate")
    pv.add_argument("path")
    pv.set_defaults(func=cmd_validate)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
