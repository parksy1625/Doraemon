#!/usr/bin/env python3
"""Build a Doraemon gadget catalog from committed static name batches only."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "gadgets.seed.json"
UPSTREAM = ROOT / "data" / "upstream"
OUT = ROOT / "data" / "master-static.json"
DUPES = ROOT / "data" / "duplicate-candidates.generated.json"


def norm(value: str | None) -> str:
    s = unicodedata.normalize("NFKC", value or "").strip().casefold()
    return re.sub(r"[\s\-_()\[\]{}'\".,:/]+", "", s)


def load_records():
    rows = []
    for path in sorted(UPSTREAM.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload.get("records", []):
            if not isinstance(item, dict):
                continue
            en = (item.get("name_en") or "").strip()
            jp = (item.get("name_jp") or "").strip()
            if en or jp:
                rows.append({"name_en": en, "name_jp": jp, "batch": path.name})
    return rows


def main():
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    rows = load_records()

    seed_by_key = {}
    reserved_ids = set()
    for item in seed:
        if item.get("id"):
            reserved_ids.add(item["id"])
        for name in [item.get("name_jp"), item.get("name_en"), *(item.get("aliases") or [])]:
            if name:
                seed_by_key[norm(name)] = item

    groups = {}
    for row in rows:
        key = norm(row["name_jp"]) or norm(row["name_en"])
        groups.setdefault(key, []).append(row)

    duplicate_groups = []
    for key, values in groups.items():
        names = sorted({v["name_en"] for v in values if v["name_en"]})
        if len(names) > 1:
            duplicate_groups.append({
                "key": key,
                "name_jp": next((v["name_jp"] for v in values if v["name_jp"]), ""),
                "names_en": names,
                "status": "review"
            })

    used_ids = set()
    next_id = 1
    gadgets = []

    def alloc_id():
        nonlocal next_id
        while True:
            candidate = f"DORA-GADGET-{next_id:04d}"
            next_id += 1
            if candidate not in reserved_ids and candidate not in used_ids:
                used_ids.add(candidate)
                return candidate

    for key, values in sorted(groups.items(), key=lambda kv: kv[0]):
        seed_item = None
        for value in values:
            seed_item = seed_by_key.get(norm(value["name_jp"])) or seed_by_key.get(norm(value["name_en"]))
            if seed_item:
                break
        if seed_item:
            record = json.loads(json.dumps(seed_item, ensure_ascii=False))
            used_ids.add(record["id"])
        else:
            primary = values[0]
            aliases = sorted({v["name_en"] for v in values[1:] if v["name_en"] and v["name_en"] != primary["name_en"]})
            record = {
                "id": alloc_id(),
                "name_ko": None,
                "name_jp": primary["name_jp"],
                "name_en": primary["name_en"],
                "aliases": aliases,
                "summary": "",
                "media_origin": ["unknown"],
                "categories": [],
                "capabilities": [],
                "sources": [{"name": "static-upstream-batches", "url": "data/upstream/", "note": ", ".join(sorted({v['batch'] for v in values}))}],
                "engineering": {"analyzed": False, "feasibility": None, "project_id": None}
            }
        gadgets.append(record)

    existing = {norm(g.get("name_jp")) or norm(g.get("name_en")) for g in gadgets}
    for item in seed:
        key = norm(item.get("name_jp")) or norm(item.get("name_en"))
        if key and key not in existing:
            gadgets.append(item)

    gadgets.sort(key=lambda g: (g.get("name_jp") or g.get("name_en") or "").casefold())
    OUT.write_text(json.dumps({
        "catalog_version": "0.4-static",
        "generated": True,
        "upstream_row_count": len(rows),
        "unique_upstream_keys": len(groups),
        "record_count": len(gadgets),
        "gadgets": gadgets
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DUPES.write_text(json.dumps({"groups": duplicate_groups}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"rows={len(rows)} unique={len(groups)} catalog={len(gadgets)} duplicates={len(duplicate_groups)}")


if __name__ == "__main__":
    main()
