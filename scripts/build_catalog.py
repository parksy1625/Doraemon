#!/usr/bin/env python3
"""Build a normalized Doraemon gadget catalog from public source datasets."""
from __future__ import annotations

import base64
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
        "raw_url": "https://raw.githubusercontent.com/Yobubble/doraemon-gadgets-search-engine/main/documents/base.json",
        "api_url": "https://api.github.com/repos/Yobubble/doraemon-gadgets-search-engine/contents/documents/base.json?ref=main",
    },
    {
        "name": "Yobubble base2",
        "raw_url": "https://raw.githubusercontent.com/Yobubble/doraemon-gadgets-search-engine/main/documents/base2.json",
        "api_url": "https://api.github.com/repos/Yobubble/doraemon-gadgets-search-engine/contents/documents/base2.json?ref=main",
    },
]

ROMAJI_RE = re.compile(r"[A-Za-zĀ-ž'\- ]{3,}$")
HEADERS = {"User-Agent": "Doraemon-Research-Catalog/0.3", "Accept": "application/vnd.github+json"}


def get_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read()


def fetch_source(src: dict):
    errors = []
    try:
        return json.loads(get_bytes(src["raw_url"]).decode("utf-8")), "raw"
    except Exception as e:
        errors.append(f"raw: {e}")
    try:
        meta = json.loads(get_bytes(src["api_url"]).decode("utf-8"))
        if meta.get("encoding") == "base64" and meta.get("content"):
            payload = base64.b64decode(meta["content"].replace("\n", ""))
            return json.loads(payload.decode("utf-8")), "github_api"
        if meta.get("download_url"):
            return json.loads(get_bytes(meta["download_url"]).decode("utf-8")), "github_api_download"
    except Exception as e:
        errors.append(f"api: {e}")
    raise RuntimeError("; ".join(errors))


def norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKC", s or "").strip().casefold()
    return re.sub(r"[\s\-_()\[\]{}'\".,:/]+", "", s)


def jp_only(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    m = ROMAJI_RE.search(raw)
    if m and m.start() > 0:
        candidate = raw[:m.start()].strip(" ,-/()\"")
        if candidate:
            return candidate
    return raw


def load_seed():
    data = json.loads(SEED.read_text(encoding="utf-8")) if SEED.exists() else []
    return data if isinstance(data, list) else data.get("gadgets", [])


def source_pointer(src: dict, transport: str):
    return {
        "name": src["name"],
        "url": "https://github.com/Yobubble/doraemon-gadgets-search-engine/tree/main/documents",
        "note": f"Imported factual name metadata via {transport}; descriptions are not republished.",
    }


def main():
    rows, errors, stats = [], [], []
    for src in SOURCES:
        try:
            data, transport = fetch_source(src)
            if isinstance(data, dict):
                data = data.get("gadgets") or data.get("items") or []
            accepted = 0
            for item in data:
                if not isinstance(item, dict):
                    continue
                en = (item.get("eng_name") or item.get("name_en") or "").strip()
                jp = jp_only((item.get("jp_name") or item.get("name_jp") or "").strip())
                if not en and not jp:
                    continue
                rows.append({"name_en": en, "name_jp": jp, "source": source_pointer(src, transport)})
                accepted += 1
            stats.append({"source": src["name"], "transport": transport, "rows": accepted})
        except Exception as e:
            errors.append({"source": src["name"], "error": str(e)})

    merged = {}
    for r in rows:
        key = norm(r["name_jp"]) or norm(r["name_en"])
        if not key:
            continue
        cur = merged.setdefault(key, {"name_en": r["name_en"], "name_jp": r["name_jp"], "aliases": [], "sources": []})
        if r["name_en"] and cur["name_en"] and norm(r["name_en"]) != norm(cur["name_en"]) and r["name_en"] not in cur["aliases"]:
            cur["aliases"].append(r["name_en"])
        if r["source"] not in cur["sources"]:
            cur["sources"].append(r["source"])

    seeds = load_seed()
    seed_index = {}
    reserved_ids = {s.get("id") for s in seeds if s.get("id")}
    for s in seeds:
        for candidate in (s.get("name_jp"), s.get("name_en"), *(s.get("aliases") or [])):
            if candidate:
                seed_index[norm(candidate)] = s

    gadgets, used_seed_ids = [], set()
    next_id = 1

    def new_id():
        nonlocal next_id
        while True:
            candidate = f"DORA-GADGET-{next_id:04d}"
            next_id += 1
            if candidate not in reserved_ids:
                return candidate

    for item in sorted(merged.values(), key=lambda x: (x["name_jp"] or x["name_en"]).casefold()):
        seed = seed_index.get(norm(item["name_jp"])) or seed_index.get(norm(item["name_en"]))
        if seed:
            record = json.loads(json.dumps(seed, ensure_ascii=False))
            record["sources"] = record.get("sources", []) + [s for s in item["sources"] if s not in record.get("sources", [])]
            used_seed_ids.add(seed.get("id"))
        else:
            record = {
                "id": new_id(), "name_ko": None, "name_jp": item["name_jp"], "name_en": item["name_en"],
                "aliases": item["aliases"], "summary": "", "media_origin": ["unknown"], "categories": [],
                "capabilities": [], "sources": item["sources"],
                "engineering": {"analyzed": False, "feasibility": None, "project_id": None},
            }
        gadgets.append(record)

    existing = {(norm(g.get("name_jp")), norm(g.get("name_en"))) for g in gadgets}
    for s in seeds:
        key = (norm(s.get("name_jp")), norm(s.get("name_en")))
        if key not in existing and s.get("id") not in used_seed_ids:
            gadgets.append(s)

    gadgets.sort(key=lambda g: (g.get("name_jp") or g.get("name_en") or "").casefold())
    payload = {
        "catalog_version": "0.3",
        "generated": True,
        "record_count": len(gadgets),
        "upstream_rows": len(rows),
        "source_stats": stats,
        "source_errors": errors,
        "gadgets": gadgets,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"record_count": len(gadgets), "upstream_rows": len(rows), "errors": errors}, ensure_ascii=False))
    if len(gadgets) <= len(seeds):
        raise SystemExit("No upstream gadget records were imported; refusing to publish seed-only master.json")


if __name__ == "__main__":
    main()
