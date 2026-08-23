#!/usr/bin/env python3
"""Build a normalized Doraemon gadget catalog from public source datasets.

This importer intentionally keeps only compact factual metadata such as names and
source pointers. It does not republish third-party long-form descriptions.
"""

from __future__ import annotations

import json
import re
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "master.json"
SEED = ROOT / "data" / "gadgets.seed.json"

SOURCES = [
    {
        "name": "Yobubble base",
        "url": "https://raw.githubusercontent.com/Yobubble/doraemon-gadgets-search-engine/main/documents/base.json",
    },
    {
        "name": "Yobubble base2",
        "url": "https://raw.githubusercontent.com/Yobubble/doraemon-gadgets-search-engine/main/documents/base2.json",
    },
]

ROMAJI_RE = re.compile(r"[A-Za-zĀ-ž'\- ]{3,}$")


def fetch_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Doraemon-Research-Catalog/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").strip().casefold()
    return re.sub(r"[\s\-_()\[\]{}'\".,:/]+", "", s)


def jp_only(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    # Most upstream rows are '日本語 Romaji'. Remove only a trailing Latin reading.
    m = ROMAJI_RE.search(raw)
    if m and m.start() > 0:
        candidate = raw[: m.start()].strip(" ,-/()\"")
        if candidate:
            return candidate
    return raw


def load_seed():
    if not SEED.exists():
        return []
    data = json.loads(SEED.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("gadgets", [])


def main():
    rows = []
    errors = []
    for src in SOURCES:
        try:
            data = fetch_json(src["url"])
            if isinstance(data, dict):
                data = data.get("gadgets") or data.get("items") or []
            for item in data:
                en = (item.get("eng_name") or item.get("name_en") or "").strip()
                jp_raw = (item.get("jp_name") or item.get("name_jp") or "").strip()
                if not en and not jp_raw:
                    continue
                rows.append({
                    "name_en": en,
                    "name_jp": jp_only(jp_raw),
                    "source": src,
                })
        except Exception as e:
            errors.append({"source": src["name"], "error": str(e)})

    # Merge duplicate upstream rows primarily by Japanese name, secondarily English.
    merged = {}
    for r in rows:
        key = norm(r["name_jp"]) or norm(r["name_en"])
        if not key:
            continue
        cur = merged.setdefault(key, {
            "name_en": r["name_en"],
            "name_jp": r["name_jp"],
            "aliases": [],
            "sources": [],
        })
        if r["name_en"] and r["name_en"] != cur["name_en"] and r["name_en"] not in cur["aliases"]:
            cur["aliases"].append(r["name_en"])
        if r["source"] not in cur["sources"]:
            cur["sources"].append(r["source"])

    # Seed records are authoritative curated overrides and are merged when possible.
    seeds = load_seed()
    seed_index = {}
    for s in seeds:
        for candidate in [s.get("name_jp"), s.get("name_en")]:
            if candidate:
                seed_index[norm(candidate)] = s

    ordered = sorted(merged.values(), key=lambda x: (x["name_jp"] or x["name_en"]).casefold())
    gadgets = []
    used_seed_ids = set()
    counter = 1
    for item in ordered:
        seed = seed_index.get(norm(item["name_jp"])) or seed_index.get(norm(item["name_en"]))
        if seed:
            record = dict(seed)
            record["sources"] = record.get("sources", []) + [s for s in item["sources"] if s not in record.get("sources", [])]
            used_seed_ids.add(seed.get("id"))
        else:
            while f"DORA-GADGET-{counter:04d}" in used_seed_ids:
                counter += 1
            record = {
                "id": f"DORA-GADGET-{counter:04d}",
                "name_ko": None,
                "name_jp": item["name_jp"],
                "name_en": item["name_en"],
                "aliases": item["aliases"],
                "summary": "",
                "media_origin": ["unknown"],
                "categories": [],
                "capabilities": [],
                "sources": item["sources"],
                "engineering": {"analyzed": False, "feasibility": None, "project_id": None},
            }
            counter += 1
        gadgets.append(record)

    # Include curated seed items absent from upstream.
    existing_keys = {norm(g.get("name_jp")) or norm(g.get("name_en")) for g in gadgets}
    for s in seeds:
        k = norm(s.get("name_jp")) or norm(s.get("name_en"))
        if k and k not in existing_keys:
            gadgets.append(s)

    payload = {
        "catalog_version": "0.2",
        "generated": True,
        "record_count": len(gadgets),
        "source_errors": errors,
        "gadgets": gadgets,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(gadgets)} records to {OUT}")
    if errors:
        print("Warnings:", json.dumps(errors, ensure_ascii=False))


if __name__ == "__main__":
    main()
