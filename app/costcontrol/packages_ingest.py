"""Parse Package Register markdown files and upsert packages + workstreams."""
from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy.orm import Session

from .models import Package, PackageScheduleStage, Workstream
from .seed import SCHEDULE_STAGES


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------

def _parse_one(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Project number from heading: "# Package Register — 5055: ..."
    proj_num = None
    for line in lines[:6]:
        m = re.match(r"#\s+Package Register\s*[—\-]+\s*(\d+)", line)
        if m:
            proj_num = m.group(1)
            break
    if not proj_num:
        return None

    # ── Package Register table ──────────────────────────────────────────
    packages_raw: list[dict] = []
    in_pkg_section = False
    header_seen = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"##\s+Package Register", stripped):
            in_pkg_section = True
            header_seen = False
            continue
        if in_pkg_section:
            if stripped.startswith("##") and not stripped.startswith("## Package"):
                break
            if "|" not in stripped:
                continue
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if not cells:
                continue
            if all(re.match(r"[-:]+$", c) for c in cells if c):
                continue
            if cells[0] in ("Package No.", "Package Number"):
                header_seen = True
                continue
            if header_seen and len(cells) >= 4 and cells[0]:
                packages_raw.append({
                    "package_number": cells[0],
                    "description":    cells[1],
                    "package_type":   cells[2],
                    "package_stage":  cells[3],
                })

    # ── Workstream Register sections ─────────────────────────────────────
    # Each section starts with: ### <pkg_number> — <description>
    workstream_data: dict[str, dict] = {}
    i = 0
    while i < len(lines):
        m = re.match(r"###\s+(\S+)\s+[—\-]+\s+(.+)", lines[i])
        if m:
            pkg_num = m.group(1)
            j = i + 1
            pkg_type = None
            std_applied = None
            scope_parts: list[str] = []
            workstreams: list[dict] = []
            ws_order = 0

            while j < len(lines):
                line = lines[j]
                stripped = line.strip()
                # Next section boundary
                if stripped.startswith("###") or (stripped.startswith("##") and not stripped.startswith("###")):
                    break
                # Type / Standard line
                if "**Package Type:**" in stripped:
                    m2 = re.search(r"\*\*Package Type:\*\*\s*([^|*\n]+)", stripped)
                    if m2:
                        pkg_type = m2.group(1).strip()
                    m3 = re.search(r"\*\*Standard Applied:\*\*\s*([^|*\n]+)", stripped)
                    if m3:
                        std_applied = m3.group(1).strip()
                # Scope summary
                elif "**Scope Summary:**" in stripped:
                    text_after = re.sub(r"\*\*Scope Summary:\*\*\s*", "", stripped).strip()
                    if text_after:
                        scope_parts.append(text_after)
                # Workstream table row — only rows whose first cell starts "WS-"
                elif "|" in stripped:
                    cells = [c.strip() for c in stripped.split("|")[1:-1]]
                    if cells and re.match(r"WS-\d+", cells[0]):
                        ws_desc = cells[1] if len(cells) > 1 else ""
                        workstreams.append({
                            "ref":          cells[0],
                            "description":  ws_desc,
                            "display_order": ws_order,
                        })
                        ws_order += 1
                j += 1

            workstream_data[pkg_num] = {
                "pkg_type":     pkg_type,
                "std_applied":  std_applied,
                "scope_summary": " ".join(scope_parts) if scope_parts else None,
                "workstreams":  workstreams,
            }
            i = j
        else:
            i += 1

    # ── Merge ────────────────────────────────────────────────────────────
    packages: list[dict] = []
    for order, raw in enumerate(packages_raw):
        num = raw["package_number"]
        ws = workstream_data.get(num, {})
        packages.append({
            "package_number":      num,
            "description":         raw["description"],
            "package_type":        ws.get("pkg_type") or raw["package_type"],
            "package_stage":       raw["package_stage"],
            "scope_summary":       ws.get("scope_summary"),
            "estimation_standard": ws.get("std_applied"),
            "display_order":       order,
            "workstreams":         ws.get("workstreams", []),
        })

    return {"project_number": proj_num, "packages": packages}


def parse_package_registers(register_dir: Path) -> list[dict]:
    results = []
    for path in sorted(register_dir.glob("*.md")):
        data = _parse_one(path)
        if data:
            results.append(data)
    return results


# ---------------------------------------------------------------------------
# DB upsert
# ---------------------------------------------------------------------------

_STAGE_ORDER = {s: i for i, s in enumerate(SCHEDULE_STAGES)}


def seed_packages(db: Session, register_dir: Path) -> None:
    if not register_dir.exists():
        return

    all_data = parse_package_registers(register_dir)

    for proj_data in all_data:
        proj_num = proj_data["project_number"]
        for pkg_data in proj_data["packages"]:
            num = pkg_data["package_number"]
            pkg = db.query(Package).filter_by(package_number=num).first()

            if pkg is None:
                pkg = Package(
                    package_number=num,
                    project_number=proj_num,
                    description=pkg_data["description"],
                    package_type=pkg_data["package_type"],
                    package_stage=pkg_data["package_stage"],
                    scope_summary=pkg_data["scope_summary"],
                    estimation_standard=pkg_data["estimation_standard"],
                    display_order=pkg_data["display_order"],
                )
                db.add(pkg)
                db.flush()

                # Eager: pre-insert the 4 schedule stage rows (all null)
                for stage in SCHEDULE_STAGES:
                    db.add(PackageScheduleStage(
                        package_id=pkg.id,
                        stage=stage,
                        stage_order=_STAGE_ORDER[stage],
                    ))
            else:
                pkg.description        = pkg_data["description"]
                pkg.package_type       = pkg_data["package_type"]
                pkg.package_stage      = pkg_data["package_stage"]
                pkg.scope_summary      = pkg_data["scope_summary"]
                pkg.estimation_standard = pkg_data["estimation_standard"]
                pkg.display_order      = pkg_data["display_order"]

            db.flush()

            # Upsert workstreams
            existing = {w.ref: w for w in db.query(Workstream).filter_by(package_id=pkg.id).all()}
            seen: set[str] = set()
            for ws in pkg_data["workstreams"]:
                ref = ws["ref"]
                seen.add(ref)
                if ref in existing:
                    existing[ref].description  = ws["description"]
                    existing[ref].display_order = ws["display_order"]
                else:
                    db.add(Workstream(
                        package_id=pkg.id,
                        ref=ws["ref"],
                        description=ws["description"],
                        display_order=ws["display_order"],
                    ))
            for ref, ws_obj in existing.items():
                if ref not in seen:
                    db.delete(ws_obj)

    db.commit()
