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

# Länder als grobe Rechtecke, aufgeteilt in 1,5° Stücke, damit jede Abfrage schnell bleibt
REGIONS = {"DE": (47.2, 5.8, 55.1, 15.1), "AT": (46.3, 9.5, 49.1, 17.2), "FR": (41.3, -5.2, 51.1, 9.6)}

def boxes(countries, step=1.5):
    seen = set()
    for c in countries:
        s0, w0, n0, e0 = REGIONS[c]
        lat = s0
        while lat < n0:
            lng = w0
            while lng < e0:
                key = (round(math.floor(lat/step)*step, 2), round(math.floor(lng/step)*step, 2))
                if key not in seen:
                    seen.add(key); yield (key[0], key[1], key[0]+step, key[1]+step)
                lng += step
            lat += step

def query(b):
    bb = f"{b[0]},{b[1]},{b[2]},{b[3]}"
    return f"""[out:json][timeout:180];
nwr[amenity=fuel]({bb})->.f;
(.f; nwr(around.f:80)[amenity~"^({NEAR})$"];);
out center tags;"""

def fetch(q):
    data = urllib.parse.urlencode({"data": q}).encode()
    last = None
    for url in SERVERS:
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=data, headers={"User-Agent": "Spritfuchs-Daten/1.0 (github.com/alasfaba-creator/spritfuchs-daten)"})
                with urllib.request.urlopen(req, timeout=240) as r:
                    return json.load(r)
            except Exception as e:
                last = e; print("Fehler", url, e, file=sys.stderr); time.sleep(20 * (attempt + 1))
    raise SystemExit(f"Overpass nicht erreichbar: {last}")

def tk(lat, lng):
    return f"{math.floor(lat*10)}_{math.floor(lng*10)}"

def main():
    out = os.path.join(sys.argv[1], "v1", "osm")
    countries = sys.argv[2:] or ["DE", "AT", "FR"]
    tiles = {}
    total = 0
    done = set()
    bl = list(boxes(countries))
    for i, b in enumerate(bl):
        j = fetch(query(b)); time.sleep(1)
        print(f"Stück {i+1}/{len(bl)}: {len(j.get('elements', []))} Einträge", file=sys.stderr)
        for e in j.get("elements", []):
            uid = (e.get("type"), e.get("id"))
            if uid in done: continue
            done.add(uid)
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
    os.makedirs(out, exist_ok=True)
    for old in glob.glob(os.path.join(out, "*.json")): os.remove(old)
    for k, v in tiles.items():
        with open(os.path.join(out, k + ".json"), "w", encoding="utf-8") as fh:
            json.dump(v, fh, ensure_ascii=False, separators=(",", ":"))
    print(json.dumps({"tankstellen": total, "kacheln": len(tiles)}))

if __name__ == "__main__":
    main()
