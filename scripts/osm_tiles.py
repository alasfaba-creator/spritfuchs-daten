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
NEAR = "car_wash|charging_station|compressed_air|vacuum_cleaner"

# Länder als grobe Rechtecke, aufgeteilt in 1,5° Stücke, damit jede Abfrage schnell bleibt
REGIONS = {"DE": (47.2, 5.8, 55.1, 15.1), "DEN": (51.0, 5.8, 55.1, 15.1), "DES": (47.2, 5.8, 51.0, 15.1), "AT": (46.3, 9.5, 49.1, 17.2),
           "FRN": (46.2, -5.2, 51.1, 8.3), "FRS": (41.3, -2.0, 46.2, 9.6)}

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
    # ohne "around": schneller und schonender für die Overpass Server
    return f"""[out:json][timeout:120];
(nwr[amenity=fuel]({bb}); nwr[amenity~"^({NEAR})$"]({bb}););
out center tags;"""

def fetch(q):
    """Ein Versuch je Server, kurze Wartezeit. Fehlschläge werden übersprungen statt endlos zu warten."""
    data = urllib.parse.urlencode({"data": q}).encode()
    for url in SERVERS:
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": "Spritfuchs-Daten/1.0 (github.com/alasfaba-creator/spritfuchs-daten)"})
            with urllib.request.urlopen(req, timeout=130) as r:
                return json.load(r)
        except Exception as e:
            print("Fehler", url, e, file=sys.stderr, flush=True)
            time.sleep(5)
    return None

def tk(lat, lng):
    return f"{math.floor(lat*10)}_{math.floor(lng*10)}"

LIVE = "https://alasfaba-creator.github.io/spritfuchs-daten/v1/osm/"

def previous_tiles(b):
    """Letzter veröffentlichter Stand für ein Gebiet, falls die neue Abfrage scheitert."""
    out = {}
    for a10 in range(int(round(b[0]*10)), int(round(b[2]*10))):
        for o10 in range(int(round(b[1]*10)), int(round(b[3]*10))):
            k = f"{a10}_{o10}"
            try:
                with urllib.request.urlopen(LIVE + k + ".json", timeout=20) as r:
                    out[k] = json.load(r)
            except Exception:
                pass
    return out

def fetch_box(b, depth=0):
    """Abfrage für ein Gebiet; klappt sie nicht, wird das Gebiet geviertelt und erneut versucht."""
    j = fetch(query(b)); time.sleep(2)
    if j is not None:
        return j.get("elements", [])
    if depth >= 1:
        return None
    mlat, mlng = (b[0]+b[2])/2, (b[1]+b[3])/2
    parts = [(b[0], b[1], mlat, mlng), (b[0], mlng, mlat, b[3]), (mlat, b[1], b[2], mlng), (mlat, mlng, b[2], b[3])]
    els = []
    for q in parts:
        r = fetch_box(q, depth+1)
        if r is None:
            return None
        els += r
    return els

def main():
    out = os.path.join(sys.argv[1], "v1", "osm")
    tag = "_".join(sys.argv[2:]) or "alle"
    countries = sys.argv[2:] or ["DE", "AT", "FRN", "FRS"]
    tiles = {}
    total = 0
    done = set()
    bl = list(boxes(countries))
    started = time.time(); ok = fail = kept = 0
    for i, b in enumerate(bl):
        els = None
        if time.time() - started < 36 * 60:
            els = fetch_box(b)
        if els is None:
            # alten Stand behalten statt das Gebiet leer zu lassen
            prev = previous_tiles(b)
            for k, v in prev.items():
                tiles.setdefault(k, {"f": [], "n": []})
                tiles[k]["f"] += v.get("f", []); tiles[k]["n"] += v.get("n", [])
                total += len(v.get("f", []))
            fail += 1; kept += 1 if prev else 0
            print(f"Stück {i+1}/{len(bl)}: alter Stand übernommen ({len(prev)} Kacheln)", file=sys.stderr, flush=True)
            continue
        ok += 1
        print(f"Stück {i+1}/{len(bl)}: {len(els)} Einträge", file=sys.stderr, flush=True)
        for e in els:
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
    for k, v in tiles.items():
        with open(os.path.join(out, k + ".json"), "w", encoding="utf-8") as fh:
            json.dump(v, fh, ensure_ascii=False, separators=(",", ":"))
    status = {"tankstellen": total, "kacheln": len(tiles), "stuecke_ok": ok, "stuecke_fehler": fail, "alter_stand": kept,
              "dauer_min": round((time.time()-started)/60, 1), "stand": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}
    with open(os.path.join(sys.argv[1], "v1", f"osm_status_{tag}.json"), "w") as fh: json.dump(status, fh)
    print(json.dumps(status))

if __name__ == "__main__":
    main()
