#!/usr/bin/env python3
"""Erzeugt ein kleines Beispielarchiv im Tankerkönig Format zum Testen von build_tiles.py."""
import csv, os, random, sys
from datetime import date, datetime, timedelta
root=sys.argv[1]; end=date.fromisoformat(sys.argv[2]); random.seed(1)
st=[(f"00000000-0000-0000-0000-{i:012d}", 51.2+random.random()*0.15, 6.95+random.random()*0.2) for i in range(40)]
d=os.path.join(root,"stations",f"{end:%Y}",f"{end:%m}"); os.makedirs(d,exist_ok=True)
with open(os.path.join(d,f"{end:%Y-%m-%d}-stations.csv"),"w",newline="") as f:
    w=csv.writer(f); w.writerow(["uuid","name","brand","street","house_number","post_code","city","latitude","longitude","first_active","openingtimes_json"])
    for u,la,lo in st: w.writerow([u,"Test","ARAL","Weg","1","42103","Wuppertal",la,lo,"",""])
for k in range(9):
    day=end-timedelta(days=8-k); d=os.path.join(root,"prices",f"{day:%Y}",f"{day:%m}"); os.makedirs(d,exist_ok=True)
    with open(os.path.join(d,f"{day:%Y-%m-%d}-prices.csv"),"w",newline="") as f:
        w=csv.writer(f); w.writerow(["date","station_uuid","diesel","e5","e10","dieselchange","e5change","e10change"])
        rows=[]
        for u,_,_ in st:
            base=1.6+random.random()*0.15
            for h,dv in [(0,0.03),(6,0.01),(11,-0.02),(12,0.16),(15,0.08),(18,0.0),(21,0.02)]:
                t=datetime(day.year,day.month,day.day,h,random.randint(0,59),random.randint(0,59))
                rows.append([t.strftime("%Y-%m-%d %H:%M:%S+02"),u,f"{base+dv:.3f}",f"{base+dv+0.09:.3f}","0.000" if u.endswith("7") else f"{base+dv+0.03:.3f}","1","1","1"])
        rows.sort(); w.writerows(rows)
print("ok")
