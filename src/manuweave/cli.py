"""Machine-readable local tools for host-agent orchestration."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .io import read_json, write_json


def parser():
    root = argparse.ArgumentParser(prog="manuweave")
    root.add_argument("--version", action="version", version=f"ManuWeave {__version__}")
    subs = root.add_subparsers(dest="command", required=True)
    subs.add_parser("doctor")
    presets = subs.add_parser("presets").add_subparsers(dest="action", required=True)
    presets.add_parser("list")
    presets.add_parser("catalog")
    p = presets.add_parser("verify")
    p.add_argument("name")
    p = presets.add_parser("test")
    p.add_argument("name", nargs="?", default="all")
    p.add_argument("--output", required=True)
    for action in ("show", "export"):
        p = presets.add_parser(action)
        p.add_argument("name")
        if action == "export":
            p.add_argument("--output", required=True)
    p = presets.add_parser("import")
    p.add_argument("source")
    p.add_argument("--library", required=True)
    p = subs.add_parser("learn-style")
    p.add_argument("source")
    p.add_argument("--output", required=True)
    for name in ("inspect", "analyze-missing"):
        p = subs.add_parser(name)
        p.add_argument("source")
        p.add_argument("--output")
    for name in ("plan", "run"):
        p = subs.add_parser(name)
        p.add_argument("source")
        choice = p.add_mutually_exclusive_group(required=True)
        choice.add_argument("--preset")
        choice.add_argument("--reference")
        p.add_argument("--output", required=True)
        if name == "plan":
            p.add_argument("--roles")
    for name in ("apply", "repair"):
        p = subs.add_parser(name)
        p.add_argument("plan")
        p.add_argument("--output", required=True)
        if name == "repair":
            p.add_argument("--max-rounds", type=int, default=2)
    p = subs.add_parser("audit")
    p.add_argument("before")
    p.add_argument("after")
    p.add_argument("--profile")
    p.add_argument("--output")
    p = subs.add_parser("render")
    p.add_argument("source")
    p.add_argument("--output", required=True)
    p.add_argument("--renderer", choices=["auto", "word", "libreoffice"], default="auto")
    p.add_argument("--profile")
    p = subs.add_parser("resume")
    p.add_argument("state")
    p = subs.add_parser("complete")
    p.add_argument("source")
    p.add_argument("--request", required=True)
    p.add_argument("--output", required=True)
    p = subs.add_parser("convert")
    p.add_argument("source")
    p.add_argument("--output", required=True)
    p = subs.add_parser("schema")
    p.add_argument("--output", required=True)
    p = subs.add_parser("accept")
    p.add_argument("state")
    p.add_argument("--review", required=True)
    p = subs.add_parser("refresh-fields")
    p.add_argument("source")
    p.add_argument("--output", required=True)
    p.add_argument("--max-rounds", type=int, default=3)
    return root


def execute(args):
    from . import pipeline
    from . import presets
    command = args.command
    if command == "doctor":
        from .render import doctor
        return doctor()
    if command == "presets":
        if args.action == "list":
            return presets.list_presets()
        if args.action == "catalog":
            return presets.template_catalog()
        if args.action == "verify":
            from .templates import validate_template
            profile = presets.load_preset(args.name)
            if "template" not in profile:
                return {"status": "NOT_APPLICABLE", "reason": "Generic preset; no official template provenance assertion"}
            validate_template(profile)
            return {"status": "PASS", "scope": "Source metadata, schema and pinned asset hashes only", "id": profile["id"], "template": profile["template"]}
        if args.action == "test":
            from .matrix import run_matrix
            return run_matrix(Path(args.output), None if args.name == "all" else [args.name])
        if args.action == "import":
            return presets.import_preset(Path(args.source), Path(args.library))
        profile = presets.load_preset(args.name)
        if args.action == "export":
            presets.export_preset(profile, Path(args.output))
            return {"output": str(Path(args.output).resolve())}
        return profile
    if command == "learn-style":
        profile = pipeline.resolve_profile(reference=args.source)
        if Path(args.output).exists():
            raise FileExistsError("Profile output already exists")
        write_json(args.output, profile)
        return {"output": str(Path(args.output).resolve()), "profile": profile}
    if command == "inspect":
        result = {"ir": pipeline.document_ir(args.source), "native": pipeline.inspect(args.source)}
    elif command == "analyze-missing":
        from .completeness import analyze_missing
        result = analyze_missing(pipeline.inspect(args.source))
    elif command in {"plan", "run"}:
        profile = pipeline.resolve_profile(args.preset, args.reference)
        if command == "run":
            return pipeline.run(args.source, args.output, profile)
        if Path(args.output).exists():
            raise FileExistsError("Plan output already exists")
        roles = read_json(args.roles)["roles"] if args.roles else None
        result = pipeline.plan(args.source, profile, roles)
    elif command in {"apply", "repair"}:
        edit_plan = read_json(args.plan)
        return pipeline.apply(edit_plan, args.output) if command == "apply" else pipeline.repair(edit_plan, args.output, args.max_rounds)
    elif command == "audit":
        result = pipeline.audit(args.before, args.after, read_json(args.profile) if args.profile else None)
    elif command == "render":
        from .render import render
        return render(args.source, args.output, read_json(args.profile) if args.profile else None, args.renderer)
    elif command == "resume":
        return pipeline.run(state_path=args.state)
    elif command == "complete":
        from .completeness import apply_completion
        return apply_completion(Path(args.source), Path(args.output), read_json(args.request))
    elif command == "convert":
        from .latex import convert
        return convert(args.source, args.output)
    elif command == "schema":
        from .models import CONTRACTS
        from .completeness import CompletionRequest
        destination = Path(args.output)
        if destination.exists():
            raise FileExistsError("Schema directory already exists")
        from .review import VisualReview
        for model in CONTRACTS + [CompletionRequest, VisualReview]:
            write_json(destination / f"{model.__name__}.schema.json", model.model_json_schema())
        return {"output": str(destination.resolve())}
    elif command == "accept":
        from .review import accept
        return accept(args.state, read_json(args.review))
    elif command == "refresh-fields":
        from .fields import refresh_fields
        return refresh_fields(args.source, args.output, args.max_rounds)
    else:
        raise ValueError(f"Unknown command {command}")
    if getattr(args, "output", None):
        if Path(args.output).exists():
            raise FileExistsError("JSON output already exists")
        write_json(args.output, result)
    return result


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    try:
        result = execute(parser().parse_args())
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        if isinstance(result, dict) and result.get("status") == "FAIL":
            return 1
    except Exception as exc:
        payload = {"status": "FAIL", "error": type(exc).__name__, "message": str(exc)}
        if hasattr(exc, "candidates"):
            payload["candidates"] = exc.candidates
        print(json.dumps(payload, ensure_ascii=False, default=str))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
