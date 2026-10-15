"""Pipeline contracts (SHAPES 3): one build/pipelines/<source>.json per source, derived from build/blueprint.json (SHAPES 2).

With no blueprint the sources come from the profile's systems and every contract is marked guessed. The schema types are "auto":
the runner infers them when it builds silver. Rule ids are "<measure>:<rule text>"."""
import logging
import re

from sh_platform.jsonfile import read_json_strict, write_json_atomic
from sh_platform.plane import CompanyPlane

log = logging.getLogger(__name__)
GUESS = {"expected": "D+1 09:00", "sla": "WD8"}  # a default, only used when nothing states it; the contract is marked guessed
NOT_YET = "Not available yet"


def slug(text) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")[:60]
    return s if re.match(r"[a-z]", s) else ("s_" + s if s else "")


def _read(plane: CompanyPlane, *parts) -> dict:
    try:
        d = read_json_strict(plane.path(*parts), dict)
    except (OSError, ValueError):
        log.warning("could not read %s", "/".join(parts))
        return {}
    return d or {}


def derive(plane: CompanyPlane) -> list[dict]:
    bp = _read(plane, "build", "blueprint.json")
    signer = next((s.get("name") for s in bp.get("signed_by", []) if s.get("name")), NOT_YET)
    out: dict[str, dict] = {}
    # The environment answers: each system's catalogue name and owner, keyed by the source id.
    systems = {slug(((i.get("name") or {}).get("value") if isinstance(i, dict) else None) or k):
               (i if isinstance(i, dict) else {}) for k, i in (_read(plane, "context", "profile", "profile.json").get("systems") or {}).items()}

    def said(src: str, key: str):
        v = (systems.get(src, {}).get(key) or {}).get("value")
        return v if isinstance(v, str) and v.strip() else None

    def make(src: str, mark: str, title: str | None = None) -> dict:
        # Owner: the environment answer for this system, else the blueprint signer. Title: the catalogue name, else the id in words.
        return out.setdefault(src, {"source": src, "title": said(src, "name") or title or src.replace("_", " ").capitalize(), "lands_at": "landing",
                                    "pattern": f"{src}*.csv", **GUESS, "schema": [], "rules": [], "depends_on": [],
                                    "owner": said(src, "owner") or signer, "marts": [], "mark": mark})
    if bp:
        for sch in bp.get("schedule", []):
            if slug(sch.get("source")):
                c = make(slug(sch["source"]), "derived", str(sch["source"]))
                c.update(expected=sch.get("expected") or c["expected"], sla=sch.get("sla") or c["sla"],
                         depends_on=[slug(d) for d in sch.get("depends_on", [])])
        for ln in bp.get("lineage", []):
            if not slug(ln.get("source")):
                continue
            c = make(slug(ln["source"]), "derived", str(ln["source"]))
            for f in ln.get("fields", []):
                if f not in [s["field"] for s in c["schema"]]:
                    c["schema"].append({"field": f, "type": "auto"})
            mart = ".".join(str(ln.get("mart", "")).split(".")[:2])
            if mart.startswith("gold.") and mart not in c["marts"]:
                c["marts"].append(mart)
            c["rules"] += [f"{r['measure']}:{r['rule']}" for r in bp.get("rules", []) if r.get("measure") == ln.get("measure")]
    else:
        for sid, item in (_read(plane, "context", "profile", "profile.json").get("systems") or {}).items():
            name = (item.get("name") or {}).get("value") if isinstance(item, dict) else None
            if slug(name or sid):
                make(slug(name or sid), "guessed")
    return sorted(out.values(), key=lambda c: c["source"])


def ensure(plane: CompanyPlane) -> list[dict]:
    """Derive the contracts and write each file that is missing or different."""
    cs = derive(plane)
    for c in cs:
        p = plane.path("build", "pipelines", f"{c['source']}.json")
        if read_json_strict(p) != c:
            write_json_atomic(p, c)
    keep = {c["source"] for c in cs}
    for f in plane.path("build", "pipelines").glob("*.json"):  # a source no longer derived leaves no contract (or commit list) behind
        if f.name.removesuffix(".commits.json").removesuffix(".json").replace("-", "_") not in keep:
            f.unlink(missing_ok=True)
    return cs
