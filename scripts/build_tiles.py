#!/usr/bin/env python3
"""
Baut aus dem Tankerkönig Preisarchiv kleine JSON Kacheln mit dem Preisverlauf
der letzten 7 Tage je Tankstelle. Die App lädt nur die Kacheln rund um den Nutzer.

Erwartete Struktur des Archivs (Tankerkönig tankerkoenig-data):
  prices/JJJJ/MM/JJJJ-MM-TT-prices.csv     date,station_uuid,diesel,e5,e10,...
  stations/JJJJ/MM/JJJJ-MM-TT-stations.csv uuid,name,brand,...,latitude,longitude,...
Spalten werden über die Kopfzeile gefunden, nicht über die Position.

Ausgabe (in OUT):
  v1/meta.json                 Stand, Zeitraum, Liste der Kacheln
  v1/tiles/<lat10>_<lng10>.json  je 0,1° x 0,1° eine Datei
Kachelformat:
  {"v":1,"from":<Minuten seit 1970 UTC>,"s":{"<uuid>":{"d":[[min,preis],...],"e5":[...],"e10":[...]}}}
  min = Minuten seit "from", preis = Euro x 1000 (ganzzahlig). Nur Preisänderungen (Stufenverlauf).
"""
import csv, glob, json, os, sys, math, argparse
from datetime import datetime, timedelta, timezone

FUELS = [("diesel", "d"), ("e5", "e5"), ("e10", "e10")]

def parse_ts(s):
    s = s.strip()
    # Formate wie "2026-10-23 06:01:12+02" oder "2026-10-23 06:01:12+02:00"
    if len(s) >= 3 and (s[-3] in "+-") and s[-2:].isdigit():
        s = s + ":00"
    s = s.replace(" ", "T", 1)
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone(timedelta(hours=1)))
    return dt.astimezone(timezone.utc)

def price(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f <= 0.5 or f > 5:   # 0 bedeutet "nicht angeboten"
        return None
    return int(round(f * 1000))

def find_col(header, *names):
    low = [h.strip().lower() for h in header]
    for n in names:
        if n in low:
            return low.index(n)
    return None

def day_file(root, kind, day):
    return os.path.join(root, kind, f"{day:%Y}", f"{day:%m}", f"{day:%Y-%m-%d}-{kind}.csv")

def latest_stations_file(root, end_day):
    for i in range(0, 40):
        f = day_file(root, "stations", end_day - timedelta(days=i))
        if os.path.exists(f):
            return f
    found = sorted(glob.glob(os.path.join(root, "stations", "*", "*", "*-stations.csv")))
    return found[-1] if found else None

def tile_key(lat, lng):
    return f"{math.floor(lat*10)}_{math.floor(lng*10)}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--end", help="letzter Tag JJJJ-MM-TT (Standard: der neueste vorhandene Tag)")
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args()

    if a.end:
        end_day = datetime.strptime(a.end, "%Y-%m-%d").date()
    else:
        files = sorted(glob.glob(os.path.join(a.archive, "prices", "*", "*", "*-prices.csv")))
        if not files:
            sys.exit("Keine Preisdateien im Archiv gefunden")
        end_day = datetime.strptime(os.path.basename(files[-1])[:10], "%Y-%m-%d").date()

    start_day = end_day - timedelta(days=a.days - 1)
    window_from = datetime(start_day.year, start_day.month, start_day.day, tzinfo=timezone(timedelta(hours=1))).astimezone(timezone.utc)
    from_min = int(window_from.timestamp() // 60)

    # Stationen: Lage für die Kacheln
    sf = latest_stations_file(a.archive, end_day)
    if not sf:
        sys.exit("Keine Stationsdatei gefunden")
    pos = {}
    with open(sf, newline="", encoding="utf-8") as fh:
        r = csv.reader(fh); h = next(r)
        iu, ila, ilo = find_col(h, "uuid", "station_uuid", "id"), find_col(h, "latitude", "lat"), find_col(h, "longitude", "lng", "lon")
        for row in r:
            try:
                lat, lng = float(row[ila]), float(row[ilo])
            except (ValueError, IndexError):
                continue
            if 47 < lat < 56 and 5 < lng < 16:
                pos[row[iu].strip()] = (lat, lng)

    # Preise: Vortag liefert den Startwert, danach jede Änderung
    series = {}   # uuid -> fuel -> [(min, preis)]
    last = {}     # uuid -> fuel -> letzter Preis vor Fensterbeginn
    for i in range(-1, a.days):
        day = start_day + timedelta(days=i)
        f = day_file(a.archive, "prices", day)
        if not os.path.exists(f):
            print("fehlt:", f, file=sys.stderr); continue
        with open(f, newline="", encoding="utf-8") as fh:
            r = csv.reader(fh); h = next(r)
            it, iu = find_col(h, "date", "timestamp"), find_col(h, "station_uuid", "uuid")
            cols = [(find_col(h, src), key) for src, key in FUELS]
            for row in r:
                try:
                    t = parse_ts(row[it]); u = row[iu].strip()
                except (ValueError, IndexError):
                    continue
                if u not in pos:
                    continue
                m = int(t.timestamp() // 60) - from_min
                for ci, key in cols:
                    if ci is None:
                        continue
                    p = price(row[ci]) if ci < len(row) else None
                    if p is None:
                        continue
                    if m < 0:
                        last.setdefault(u, {})[key] = p
                        continue
                    lst = series.setdefault(u, {}).setdefault(key, [])
                    if not lst and key in last.get(u, {}) and last[u][key] != p:
                        lst.append([0, last[u][key]])
                    if lst and lst[-1][1] == p:
                        continue
                    lst.append([m, p])

    # Stationen ohne Änderung im Fenster, aber mit Startwert
    for u, fu in last.items():
        for key, p in fu.items():
            lst = series.setdefault(u, {}).setdefault(key, [])
            if not lst:
                lst.append([0, p])

    tiles = {}
    for u, fu in series.items():
        lat, lng = pos[u]
        tiles.setdefault(tile_key(lat, lng), {})[u] = fu

    outdir = os.path.join(a.out, "v1", "tiles")
    os.makedirs(outdir, exist_ok=True)
    for old in glob.glob(os.path.join(outdir, "*.json")):
        os.remove(old)
    for k, st in tiles.items():
        with open(os.path.join(outdir, k + ".json"), "w", encoding="utf-8") as fh:
            json.dump({"v": 1, "from": from_min, "s": st}, fh, separators=(",", ":"))
    meta = {"v": 1, "updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
            "from": start_day.isoformat(), "to": end_day.isoformat(),
            "stations": len(series), "tiles": len(tiles),
            "source": "Tankerkönig (tankerkoenig.de), Markttransparenzstelle für Kraftstoffe",
            "license": "CC BY-NC-SA 4.0"}
    with open(os.path.join(a.out, "v1", "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1)
    print(json.dumps(meta, ensure_ascii=False))

if __name__ == "__main__":
    main()
