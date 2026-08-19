# Autobahn-Schutzeinrichtungs-Klassifikation (MVP)

Klassifiziert für einen gewählten Autobahnabschnitt in Deutschland, welche Art
von Schutzeinrichtung (Betonschutzwand / Stahlschutzplanke / Seilrückhaltesystem /
kein System) am Mittelstreifen verbaut ist – basierend auf Google Street View
und einem multimodalen LLM (Claude) als Zero-/Few-Shot-Klassifikator.

## Architektur

```
main.py
 ├── osm_sampling.py   → lädt Autobahn-Ways aus OpenStreetMap (Overpass API),
 │                        erzeugt äquidistante Punkte + Fahrtrichtung
 ├── streetview.py     → holt für jeden Punkt das nächste Street-View-Pano
 │                        und ein Bild senkrecht zur Fahrtrichtung
 └── classify.py       → schickt das Bild an Claude, Few-Shot-Prompting mit
                          Referenzbildern, strukturierter JSON-Output
```

## Setup

```bash
pip install -r requirements.txt

export GOOGLE_MAPS_API_KEY="dein_google_key"      # Street View Static + Metadata API aktivieren
export ANTHROPIC_API_KEY="dein_anthropic_key"
```

Für den Google-Key: In der Google Cloud Console ein Projekt anlegen, die
**Street View Static API** aktivieren und Abrechnung einrichten (die
Metadata-Abfragen sind kostenlos, nur die tatsächlichen Bildabrufe kosten).

## Referenzbilder für Few-Shot-Prompting (empfohlen)

Lege ein paar Beispielbilder pro Klasse ab, damit das Modell eine visuelle
Kalibrierung hat (verbessert die Trefferquote spürbar gegenüber reinem
Zero-Shot):

```
reference_images/
  betonschutzwand/
    beispiel1.jpg
    beispiel2.jpg
  stahlschutzplanke/
    beispiel1.jpg
  seilruckhaltesystem/
    beispiel1.jpg
  kein_system/
    beispiel1.jpg
```

2-3 Bilder pro Klasse reichen für den Start. Ohne diesen Ordner klassifiziert
das Modell rein anhand der textuellen Beschreibung im System-Prompt (siehe
`classify.py`) – funktioniert auch, aber vermutlich mit geringerer Präzision.

## Verwendung

Bounding Box um den zu untersuchenden Abschnitt herum wählen (z.B. via
[bboxfinder.com](http://bboxfinder.com)) und optional per `--ref` auf eine
bestimmte Autobahn filtern:

```bash
python main.py \
  --south 48.10 --west 11.55 --north 48.15 --east 11.65 \
  --ref A9 \
  --limit 20 \
  --out results.csv
```

`--limit` ist besonders für den ersten Test wichtig, um nicht versehentlich
hunderte kostenpflichtige Street-View-Abrufe auszulösen, bevor die Pipeline
sauber läuft.

Output: `results.csv` mit einer Zeile pro Sample-Punkt (Koordinaten, Pano-ID,
Aufnahmedatum des Panos, klassifizierte Klasse, Konfidenz, Begründung des
Modells) sowie eine Konsolen-Zusammenfassung der Klassenverteilung.

## Web-Oberfläche (Streamlit)

Neben dem CLI-Skript (`main.py`) gibt es eine Streamlit-App (`app.py`) mit
denselben Funktionen, aber interaktiv im Browser:

- Bounding Box direkt auf einer Karte einzeichnen (statt Koordinaten von Hand
  einzutippen)
- Live-Fortschrittsanzeige während der Klassifikation
- Ergebnisse als farbcodierte Marker auf einer Karte (Klick auf einen Punkt
  zeigt Klasse, Konfidenz und Begründung)
- Ergebnistabelle + CSV-Download direkt im Browser

### Lokal starten

```bash
pip install -r requirements.txt
export GOOGLE_MAPS_API_KEY="dein_key"
export ANTHROPIC_API_KEY="dein_key"
streamlit run app.py
```

## Deployment als Web-App (Cloud, ohne eigenen Server)

### Option A: Streamlit Community Cloud (empfohlen zum Start)

1. Dieses Verzeichnis in ein **GitHub-Repo** pushen (öffentlich oder privat,
   beides geht).
2. Auf [share.streamlit.io](https://share.streamlit.io) mit GitHub einloggen,
   "New app" → Repo, Branch und `app.py` als Einstiegspunkt auswählen.
3. Unter **Settings → Secrets** die Keys im TOML-Format hinterlegen (siehe
   `.streamlit/secrets.toml.example` in diesem Projekt):
   ```toml
   GOOGLE_MAPS_API_KEY = "dein_key"
   ANTHROPIC_API_KEY = "dein_key"
   ```
4. Deploy klicken – du bekommst einen öffentlichen Link
   (`https://<name>.streamlit.app`), den du z.B. mit Kommilitonen/Betreuern
   teilen kannst.

`config.py` liest die Keys automatisch aus `st.secrets`, wenn die App unter
Streamlit läuft – lokal weiterhin ganz normal über Umgebungsvariablen, ohne
Codeänderung nötig.

**Hinweis Rechenlimits:** Die kostenlose Community-Cloud-Stufe hat begrenzte
Ressourcen und schläft nach Inaktivität ein (Cold Start beim nächsten Aufruf).
Für ein MVP mit gelegentlichen, kleinen Testläufen (siehe `limit`-Parameter in
der App) völlig ausreichend.

### Option B: Hugging Face Spaces

Alternative mit denselben Grundprinzipien: Repo/Space anlegen, SDK
"Streamlit" wählen, `app.py` + `requirements.txt` hochladen, Keys unter
**Settings → Repository secrets** hinterlegen. Etwas großzügigeres kostenloses
Kontingent als Streamlit Cloud, dafür UI/Workflow etwas weniger auf
Streamlit-Apps spezialisiert.

### Option C: Eigener Cloud-Container (wenn's über das MVP hinausgeht)

Sobald mehr Kontrolle über Ressourcen/Laufzeiten nötig ist (größere
Abschnitte, viele parallele Nutzer): Dockerfile bauen und z.B. auf
**Google Cloud Run** deployen (skaliert auf 0 wenn ungenutzt, zahlst nur pro
Nutzung). Der App-Code selbst bleibt unverändert, es kommt nur eine
`Dockerfile` hinzu.

## Bekannte Einschränkungen dieses MVP (bewusst in Kauf genommen)

- **Way-Stitching ist naiv**: Bei Autobahnkreuzen/-verzweigungen werden die
  OSM-Ways einfach in Rückgabereihenfolge aneinandergehängt, nicht über einen
  echten Routing-Graphen. Für einen einzelnen, klar begrenzten Abschnitt ohne
  Kreuze funktioniert das gut; für komplexere Netzabschnitte braucht es
  später ein echtes Routing (z.B. OSRM mit `motorway`-Profil).
- **Keine Behandlung von Richtungsfahrbahnen**: Deutsche Autobahnen haben
  meist getrennte OSM-Ways pro Fahrtrichtung. Welche Seite der Mittelstreifen
  ist, hängt vom `MEDIAN_SIDE_OFFSET_DEG` in `config.py` ab – das ggf. pro
  Ausschnitt gegenprüfen/anpassen.
- **Keine Verdeckungserkennung**: Bilder mit LKWs/Vegetation vor dem
  Mittelstreifen werden aktuell nicht automatisch aussortiert; das Modell
  wird instruiert, in solchen Fällen `nicht_erkennbar` zurückzugeben, aber es
  lohnt sich, diese Fälle stichprobenartig manuell zu prüfen.
- **Kein Caching**: Jeder Lauf fragt Street View erneut ab. Bei wiederholten
  Testläufen auf demselben Abschnitt lohnt sich ein einfacher Cache über
  `pano_id`.
- **Sequentiell, kein Retry**: Für Produktionsreife fehlen Parallelisierung,
  Backoff bei Rate Limits und Persistenz in einer Datenbank statt CSV.

## Empfohlene nächste Schritte

1. Kleinen Testabschnitt (5-10 km) wählen, den du selbst kennst, um die
   Ergebnisse gegenprüfen zu können.
2. Mit `--limit 10-20` starten, Kosten und Trefferquote grob einschätzen.
3. Referenzbilder sammeln (aus den eigenen ersten Testergebnissen oder
   manuell aus Street View) und die Few-Shot-Ordnerstruktur befüllen.
4. Falsch klassifizierte Fälle sammeln und in den System-Prompt bzw. die
   Referenzbilder einfließen lassen (iterativ verbessern).
5. Erst danach über Skalierung (mehr km, Parallelisierung, Caching,
   ggf. eigenes trainiertes Modell) nachdenken.
