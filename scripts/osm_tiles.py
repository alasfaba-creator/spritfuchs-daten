#!/usr/bin/env python3
"""
Holt einmal am Tag aus OpenStreetMap alle Tankstellen in Deutschland, Österreich und
Frankreich mit Ausstattung, Zahlarten und Sorten, dazu Einrichtungen direkt daneben
(Waschanlage, Café, Ladesäule ...). Ausgabe als Kacheln wie beim Preisverlauf:
  v1/osm/<lat10>_<lng10>.json  {"f":[[lat,lng,{tags}],...],"n":[[lat,lng,"car_wash"],...]}
Daten © OpenStreetMap Mitwirkende, ODbL.
"""
import json, math, os, sys, time, urllib.request, urllib.parse, glob

SERVERS = ["https://overpass-api.de/api/interpreter",
           "https://overpass.private.coffee/api/interpreter"]
KEEP = ("payment:", "fuel:")
KEEP_EXACT = {"shop", "car_wash", "toilets", "compressed_air", "vacuum_cleaner", "opening_hours",
              "automated", "cafe", "bistro", "brand", "name"}
NEAR = "car_wash|cafe|fast_food|restaurant|charging_station|toilets|compressed_air|vacuum_cleaner"

def query(country):
    return f"""[out:json][timeout:900][maxsize:1073741824];
area["ISO3166-1"="{country}"][admin_level=2]->.a;
nwr[amenity=fuel](area.a)->.f;
(.f; nwr(around.f:80)[amenity~"^({NEAR})$"];);
out center tags;"""

def fetch(q):
    data = urllib.parse.urlencode({"data": q}).encode()
    last = None
    for url in SERVERS:
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=data, headers={"User-Agent": "Spritfuchs-Daten/1.0 (github.com/alasfaba-creator/spritfuchs-daten)"})
                with urllib.request.urlopen(req, timeout=1000) as r:
                    return json.load(r)
            except Exception as e:
                last = e; print("Fehler", url, e, file=sys.stderr); time.sleep(30 * (attempt + 1))
    raise SystemExit(f"Overpass nicht erreichbar: {last}")

def tk(lat, lng):
    return f"{math.floor(lat*10)}_{math.floor(lng*10)}"

def main():
    out = os.path.join(sys.argv[1], "v1", "osm")
    countries = sys.argv[2:] or ["DE", "AT", "FR"]
    tiles = {}
    total = 0
    for c in countries:
        j = fetch(query(c))
        for e in j.get("elements", []):
            lat = e.get("lat") or (e.get("center") or {}).get("lat")
            lng = e.get("lon") or (e.get("center") or {}).get("lon")
            if lat is None: continue
            t = e.get("tags", {})
            k = tk(lat, lng)
            tile = tiles.setdefault(k, {"f": [], "n": []})
            if t.get("amenity") == "fuel":
                keep = {kk: v for kk, v in t.items() if kk in KEEP_EXACT or kk.startswith(KEEP)}
                tile["f"].append([round(lat, 6), round(lng, 6), keep]); total += 1
            else:
                tile["n"].append([round(lat, 6), round(lng, 6), t.get("amenity")])
        print(c, "fertig", file=sys.stderr)
    os.makedirs(out, exist_ok=True)
    for old in glob.glob(os.path.join(out, "*.json")): os.remove(old)
    for k, v in tiles.items():
        with open(os.path.join(out, k + ".json"), "w", encoding="utf-8") as fh:
            json.dump(v, fh, ensure_ascii=False, separators=(",", ":"))
    print(json.dumps({"tankstellen": total, "kacheln": len(tiles)}))

if __name__ == "__main__":
    main()
