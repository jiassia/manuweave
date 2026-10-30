"""Versioned, explicitly generic academic profiles and local custom libraries."""

from __future__ import annotations

import copy
import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from .models import StyleProfile

DATA = Path(__file__).resolve().parent / "data" / "presets"
TEMPLATES = Path(__file__).resolve().parent / "data" / "templates"


class AmbiguousPresetError(ValueError):
    """A selection with more than one supported interpretation."""

    def __init__(self, candidates: list[str]):
        self.candidates = candidates
        super().__init__("Ambiguous preset; choose one of: " + ", ".join(candidates))


def _validate_profile_schema(profile: dict) -> None:
    """Validate profile metadata independently of live template asset bytes."""
    if not isinstance(profile, dict):
        raise ValueError("A profile must be a JSON object")
    for key in ("id", "name", "version", "rules", "page"):
        if key not in profile:
            raise ValueError(f"Missing profile field: {key}")
    if not isinstance(profile["version"], str) or not re.fullmatch(r"\d+\.\d+\.\d+", profile["version"]):
        raise ValueError("Profile version must use major.minor.patch")
    if not isinstance(profile["name"], str) or not profile["name"].strip():
        raise ValueError("Profile name must be nonempty")
    # Shared typed contracts cover all native Word roles, page dimensions,
    # running-header/footer formats and table borders without a second schema.
    # Validate strictly but retain omitted fields and all provenance metadata.
    StyleProfile.model_validate(profile, strict=True)
    if isinstance(profile["page"].get("columns"), bool):
        raise ValueError("Column count must be an integer, not boolean")
    formats = list(profile["rules"].values()) + list((profile.get("running") or {}).values())
    for properties in formats:
        if properties is None:
            continue
        for key, value in properties.items():
            if key in {"font", "east_asia_font"} and value is not None and not value.strip():
                raise ValueError(f"{key} must be a font name")


def validate_profile(profile: dict) -> dict:
    """Validate the profile contract and recheck current template asset bytes."""
    _validate_profile_schema(profile)
    if "template" in profile:
        # Template assets and source requirements share one owning contract.
        from .templates import validate_template

        validate_template(profile)
    return copy.deepcopy(profile)


@lru_cache(maxsize=32)
def _read_profile(path: str, mtime_ns: int, ctime_ns: int, size: int) -> dict:
    # Cache a bounded set of complete rule documents; selection keeps only small metadata.
    if size > 1_000_000:
        raise ValueError("Profile exceeds 1 MB")
    profile = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    _validate_profile_schema(profile)
    return profile


def _registry_signature():
    paths = sorted([*DATA.glob("*.json"), *TEMPLATES.glob("**/profiles/*.json")])
    result = []
    for path in paths:
        stat = path.stat()
        result.append((str(path.resolve()), stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size))
    return tuple(result)


@lru_cache(maxsize=2)
def _selection_index(signature):
    result = []
    identifiers = {}
    for descriptor in signature:
        profile = _read_profile(*descriptor)
        identifier = profile["id"]
        if identifier in identifiers:
            raise ValueError(f"Duplicate preset id {identifier}: {identifiers[identifier]} and {descriptor[0]}")
        identifiers[identifier] = descriptor[0]
        result.append({"id": identifier, "name": profile["name"], "aliases": tuple(profile.get("aliases", [])), "descriptor": descriptor})
    return tuple(sorted(result, key=lambda item: item["id"]))


def _profiles(*, verify_templates: bool = True) -> list[dict]:
    paths = [*DATA.glob("*.json"), *TEMPLATES.glob("**/profiles/*.json")]
    profiles = []
    identifiers = {}
    for path in sorted(paths):
        stat = path.stat()
        profile = copy.deepcopy(_read_profile(str(path.resolve()), stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size))
        if profile["id"] in identifiers:
            raise ValueError(f"Duplicate preset id {profile['id']}: {identifiers[profile['id']]} and {path}")
        identifiers[profile["id"]] = path
        if verify_templates and "template" in profile:
            profile = validate_profile(profile)
        profiles.append(profile)
    return sorted(profiles, key=lambda profile: profile["id"])


def _catalog_entry(profile: dict) -> dict:
    template = profile.get("template") or {}
    requirements = template.get("requirements", profile.get("requirements", []))
    coverage = template.get("coverage", profile.get("coverage"))
    if coverage is None:
        coverage = {
            "evaluation": "not_executed",
            "requirement_count": len(requirements),
            "certainty_counts": dict(sorted(Counter(requirement.get("certainty", "unknown") for requirement in requirements).items())),
            "checking_counts": dict(sorted(Counter(requirement.get("checking", "unknown") for requirement in requirements).items())),
            "role_properties": sum(len(properties) for properties in profile["rules"].values()),
            "page_properties": len(profile["page"]),
            "unknown_requirements": [requirement.get("id") for requirement in requirements if requirement.get("certainty", "unknown") == "unknown"],
            "coverage_notes": copy.deepcopy(template.get("coverage_notes", [])),
        }
        if not requirements:
            coverage["coverage_notes"].append("Normative requirement coverage has not been supplied.")
    entry = {key: profile.get(key) for key in ("id", "name", "version", "scope", "compliance")}
    entry.update({
        "aliases": profile.get("aliases", []),
        "template_family": template.get("family"),
        "source_version": template.get("source_version"),
        "engine_support": template.get("engine_support", profile.get("engine_support", {})),
        "requirements_count": len(requirements),
        "coverage": copy.deepcopy(coverage),
    })
    return entry


def list_presets() -> list[dict]:
    return [_catalog_entry(profile) for profile in _profiles()]


def template_catalog() -> list[dict]:
    """Detailed, machine-readable source and coverage records for all profiles."""
    entries = []
    for profile in _profiles():
        entry = _catalog_entry(profile)
        template = profile.get("template") or {}
        entry.update({
            "template": copy.deepcopy(template),
            "sources": copy.deepcopy(profile.get("sources", [])),
            "requirements": copy.deepcopy(template.get("requirements", profile.get("requirements", []))),
            "rules": copy.deepcopy(profile["rules"]),
            "page": copy.deepcopy(profile["page"]),
            "latex": copy.deepcopy(profile.get("latex", {})),
            "unknown": copy.deepcopy([requirement for requirement in template.get("requirements", []) if requirement.get("certainty", "unknown") == "unknown"]),
        })
        entries.append(entry)
    return entries


def _normalize(value: str) -> str:
    return re.sub(r"[\s_\-]+", "", value.casefold())


def load_preset(name_or_path: str | Path) -> dict:
    """Resolve exact IDs/aliases, then contained aliases; ambiguity is explicit."""
    path = Path(name_or_path)
    if path.is_file():
        if path.stat().st_size > 1_000_000:
            raise ValueError("Profile exceeds 1 MB")
        return validate_profile(json.loads(path.read_text(encoding="utf-8-sig")))
    value = _normalize(str(name_or_path))
    if not value:
        raise ValueError("Preset selection cannot be empty")
    # Natural-language selection reads a small index; detailed formatting and
    # provenance are loaded and checked only for the selected profile.
    profiles = _selection_index(_registry_signature())
    exact = [p for p in profiles if value in {_normalize(p["id"]), _normalize(p["name"]), *(_normalize(a) for a in p.get("aliases", []))}]
    candidates = exact or [p for p in profiles if any(_normalize(a) in value or value in _normalize(a) for a in [p["id"], p["name"], *p.get("aliases", [])])]
    if len(candidates) == 1:
        return validate_profile(_read_profile(*candidates[0]["descriptor"]))
    if len(candidates) > 1:
        raise AmbiguousPresetError([p["id"] for p in candidates])
    raise ValueError(f"Unknown preset: {name_or_path}")


def export_preset(profile: dict, destination: str | Path) -> Path:
    profile = validate_profile(profile)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(profile, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    return destination


def import_preset(path: str | Path, library_dir: str | Path) -> Path:
    profile = load_preset(path)
    return export_preset(profile, Path(library_dir) / f"{profile['id']}@{profile['version']}.json")
