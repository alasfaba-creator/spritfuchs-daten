# Spritfuchs Daten

Täglich aktualisierter Preisverlauf (7 Tage) aller deutschen Tankstellen für die App Spritfuchs.

* Ablauf: `.github/workflows/preisverlauf.yml` läuft jeden Morgen, holt das Tankerkönig Preisarchiv und baut kleine JSON Kacheln.
* Abruf: `https://<benutzer>.github.io/spritfuchs-daten/v1/tiles/<lat*10>_<lng*10>.json`
* Benötigtes Secret: `TK_ARCHIVE_URL` (Git Adresse des Tankerkönig Archivs inklusive Zugangsdaten).

Datenquelle: Tankerkönig (tankerkoenig.de), Markttransparenzstelle für Kraftstoffe. Historische Daten unter CC BY-NC-SA 4.0, nur nicht kommerzielle Nutzung.
