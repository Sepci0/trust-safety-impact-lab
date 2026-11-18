#!/usr/bin/env python3
"""Pull small dataset samples listed in datasets.json into data/<id>/.

Usage:
  python scripts/fetch.py --list                 # every dataset id, track, pull type
  python scripts/fetch.py --list --track 1       # only track 1
  python scripts/fetch.py --id llmail-inject     # default sample size from datasets.json
  python scripts/fetch.py --id llmail-inject --rows 2000
  python scripts/fetch.py --track 1              # everything fetchable for a track

Pull types:
  hf_rows  row sample via the Hugging Face dataset viewer API -> data/<id>/rows.jsonl
  socrata  DataSF query -> data/<id>/rows.json
  http     direct file download -> data/<id>/<filename>
  git      shallow clone -> data/<id>/repo/
  manual   prints the instructions from datasets.json

Set HF_TOKEN in .env (or the environment) if a gated Hugging Face dataset refuses the fetch.
Standard library only, so it runs before any pip install.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "datasets.json"
DATA = ROOT / "data"
HF_API = "https://datasets-server.huggingface.co"
HF_PAGE = 100  # the viewer API returns at most 100 rows per request
UA = "trust-safety-impact-lab-fetch/1.0"


def load_env():
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def get(url, headers=None, retries=3):
    h = {"User-Agent": UA, **(headers or {})}
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            body = e.read().decode("utf-8", "replace").strip()
            hint = "" if body.lstrip().startswith("<") else f"\n  {body[:300]}"
            raise RuntimeError(f"HTTP {e.code} for {url}{hint}") from None


def hf_headers():
    tok = os.environ.get("HF_TOKEN")
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def fetch_hf_rows(ds, spec, out, rows):
    name = spec["dataset"]
    config, split = spec.get("config"), spec.get("split")
    if config and split:
        targets = [(config, split)]
    else:
        # No split named: walk every split of the config (e.g. JBB harmful + benign),
        # sharing the row budget evenly, and tag each row with _split.
        q = urllib.parse.urlencode({"dataset": name})
        splits = json.loads(get(f"{HF_API}/splits?{q}", hf_headers()))["splits"]
        config = config or splits[0]["config"]
        targets = [(s["config"], s["split"]) for s in splits if s["config"] == config]
        if split:
            targets = [t for t in targets if t[1] == split]
    per = -(-rows // len(targets))
    path = out / "rows.jsonl"
    n = 0
    with path.open("w") as f:
        for cfg, spl in targets:
            got = 0
            for offset in range(0, per, HF_PAGE):
                q = urllib.parse.urlencode({"dataset": name, "config": cfg, "split": spl,
                                            "offset": offset, "length": min(HF_PAGE, per - offset)})
                page = json.loads(get(f"{HF_API}/rows?{q}", hf_headers())).get("rows", [])
                for r in page:
                    row = r["row"] if len(targets) == 1 else {**r["row"], "_split": spl}
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                got += len(page)
                if len(page) < HF_PAGE:
                    break
            print(f"  {name}  config={cfg}  split={spl}  rows={got}")
            n += got
    print(f"  wrote {n} rows -> {path.relative_to(ROOT)}")


def fetch_socrata(ds, spec, out, rows):
    params = dict(spec.get("params", {}))
    if rows:
        params["$limit"] = str(rows)
    url = f"https://{spec['domain']}/resource/{spec['resource']}.json?{urllib.parse.urlencode(params)}"
    data = json.loads(get(url))
    path = out / "rows.json"
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    print(f"  wrote {len(data)} rows -> {path.relative_to(ROOT)}")


def fetch_http(ds, spec, out, rows):
    names = spec.get("filenames", [])
    for i, url in enumerate(spec["urls"]):
        fname = names[i] if i < len(names) else Path(urllib.parse.urlparse(url).path).name
        path = out / fname
        path.write_bytes(get(url))
        print(f"  {path.stat().st_size / 1e6:.1f} MB -> {path.relative_to(ROOT)}")


def fetch_git(ds, spec, out, rows):
    dest = out / "repo"
    if dest.exists():
        print(f"  already cloned: {dest.relative_to(ROOT)}")
        return
    subprocess.run(["git", "clone", "--depth", "1", spec["repo"], str(dest)], check=True)


def fetch_manual(ds, spec, out, rows):
    print(f"  manual: {spec.get('instructions', '')}\n  page: {ds.get('url')}")


HANDLERS = {"hf_rows": fetch_hf_rows, "socrata": fetch_socrata, "http": fetch_http,
            "git": fetch_git, "manual": fetch_manual}


def fetch(ds, rows=None):
    spec = ds.get("fetch") or {"type": "manual"}
    kind = spec["type"]
    print(f"[{ds['id']}] {kind}")
    out = DATA / ds["id"]
    if kind != "manual":
        out.mkdir(parents=True, exist_ok=True)
    if kind == "hf_rows":
        rows = rows or spec.get("rows") or 500
    HANDLERS[kind](ds, spec, out, rows)  # socrata keeps its own $limit unless --rows is given
    if kind != "manual" and ds.get("notes"):
        print(f"  note: {ds['notes']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", action="append", help="dataset id (repeatable)")
    ap.add_argument("--track", type=int, help="track number (0-5)")
    ap.add_argument("--rows", type=int, help="override sample size for hf_rows / socrata")
    ap.add_argument("--list", action="store_true", help="list datasets and exit")
    a = ap.parse_args()
    load_env()

    catalog = json.loads(CATALOG.read_text())["datasets"]
    by_id = {d["id"]: d for d in catalog}
    sel = catalog
    if a.track is not None:
        sel = [d for d in sel if a.track in d.get("tracks", [])]
    if a.id:
        missing = [i for i in a.id if i not in by_id]
        if missing:
            sys.exit(f"unknown id(s): {', '.join(missing)}. Try --list.")
        sel = [by_id[i] for i in a.id]

    if a.list or not (a.id or a.track is not None):
        for d in sel:
            tracks = ",".join(map(str, d.get("tracks", [])))
            print(f"{d['id']:30} track {tracks:5} {d.get('fetch', {}).get('type', 'manual'):8} {d['name'][:70]}")
        if not a.list:
            print("\nPick one with --id <id> or --track <n>.")
        return

    failed = []
    for d in sel:
        try:
            fetch(d, a.rows)
        except Exception as e:  # keep going across a track
            print(f"  FAILED: {e}")
            failed.append(d["id"])
    if failed:
        sys.exit(f"\nfailed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
