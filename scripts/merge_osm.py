#!/usr/bin/env python3
"""Fügt die OSM Kacheln mehrerer Länder zusammen (Grenzkacheln enthalten beide Länder)."""
import glob, json, os, sys
src, out = sys.argv[1], sys.argv[2]
os.makedirs(os.path.join(out, "v1", "osm"), exist_ok=True)
tiles, status = {}, {}
for f in glob.glob(os.path.join(src, "*", "v1", "osm", "*.json")):
    k = os.path.basename(f); j = json.load(open(f))
    t = tiles.setdefault(k, {"f": [], "n": []}); t["f"] += j.get("f", []); t["n"] += j.get("n", [])
for f in glob.glob(os.path.join(src, "*", "v1", "osm_status_*.json")):
    status[os.path.basename(f)[11:-5]] = json.load(open(f))
if len(tiles) < 100:
    sys.exit(f"Nur {len(tiles)} OSM Kacheln, Veröffentlichung abgebrochen")
for k, t in tiles.items():
    seen = set(); t["f"] = [x for x in t["f"] if not ((x[0], x[1]) in seen or seen.add((x[0], x[1])))]
    json.dump(t, open(os.path.join(out, "v1", "osm", k), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
json.dump(status, open(os.path.join(out, "v1", "osm_status.json"), "w"), ensure_ascii=False, indent=1)
print(len(tiles), "Kacheln", json.dumps(status))
