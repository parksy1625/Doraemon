#!/usr/bin/env python3
"""Audit Doraemon static catalog for manga-core verification readiness."""
from __future__ import annotations
import json, re, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "data" / "upstream"
SEED = ROOT / "data" / "gadgets.seed.json"
OUT = ROOT / "data" / "audit-report.json"

BAD_JP = ("general information", "functionsdetails", "casual information", "relationships", "gallery")

def norm(s):
    return re.sub(r"[\s\-_()\[\]{}'\".,:/]+", "", unicodedata.normalize("NFKC", s or "").casefold())

def valid_jp(s):
    x=(s or "").strip(); low=x.casefold()
    return bool(x) and not any(t in low for t in BAD_JP) and bool(re.search(r"[ぁ-んァ-ヶ一-龯々ー]", x))

def main():
    rows=[]
    for p in sorted(UPSTREAM.glob("*.json")):
        data=json.loads(p.read_text(encoding="utf-8"))
        for r in data.get("records", []):
            if isinstance(r,dict): rows.append({**r,"batch":p.name})
    seed=json.loads(SEED.read_text(encoding="utf-8"))
    bad=[r for r in rows if r.get("name_jp") and not valid_jp(r.get("name_jp"))]
    groups={}
    for r in rows:
        key=norm(r.get("name_jp")) if valid_jp(r.get("name_jp")) else norm(r.get("name_en"))
        if key: groups.setdefault(key,[]).append(r)
    dup=[]
    for k,v in groups.items():
        ens=sorted({x.get("name_en","") for x in v if x.get("name_en")})
        if len(ens)>1: dup.append({"key":k,"names_en":ens,"name_jp":next((x.get("name_jp") for x in v if valid_jp(x.get("name_jp"))),None)})
    report={
      "version":"0.1",
      "static_rows":len(rows),
      "static_unique_keys":len(groups),
      "seed_records":len(seed),
      "invalid_japanese_name_rows":len(bad),
      "duplicate_candidate_groups":len(dup),
      "invalid_examples":bad[:30],
      "duplicate_examples":dup[:50],
      "next_gate":"Cross-check candidates against manga-first-appearance sources before marking verified_manga."
    }
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in ["static_rows","static_unique_keys","seed_records","invalid_japanese_name_rows","duplicate_candidate_groups"]},ensure_ascii=False))

if __name__=="__main__": main()
