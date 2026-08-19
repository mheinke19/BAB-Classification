"""
Zentrale Konfiguration für das Autobahn-Schutzeinrichtungs-Klassifikationssystem.

Alle Keys werden aus Umgebungsvariablen gelesen. Setze sie z.B. per:

    export GOOGLE_MAPS_API_KEY="dein_key"
    export ANTHROPIC_API_KEY="dein_key"

oder lege eine .env-Datei an (siehe README).
"""

import os


def _get_secret(key: str) -> str:
    """
    Liest einen Key zuerst aus Streamlit Secrets (falls in einer Streamlit-App
    ausgeführt, z.B. auf Streamlit Community Cloud / HF Spaces), sonst aus
    Umgebungsvariablen (lokale Ausführung / GitHub Actions / Cloud Run etc.).
    """
    try:
        import streamlit as st  # nur vorhanden, wenn Streamlit installiert ist

        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, "")


# --- API Keys ---
GOOGLE_MAPS_API_KEY = _get_secret("GOOGLE_MAPS_API_KEY")
ANTHROPIC_API_KEY = _get_secret("ANTHROPIC_API_KEY")

# --- Sampling-Parameter ---
# Abstand zwischen zwei Sample-Punkten entlang der Strecke, in Metern.
SAMPLE_DISTANCE_M = 100

# --- Street View Parameter ---
STREETVIEW_IMAGE_SIZE = "640x640"   # max. Auflösung im kostenlosen Static-API-Tier
STREETVIEW_FOV = 90                 # field of view in Grad
STREETVIEW_PITCH = 0                # 0 = Horizont, kann bei Bedarf leicht negativ sein
STREETVIEW_MAX_RADIUS_M = 50        # wie weit darf das nächste Pano vom Sample-Punkt entfernt sein

# Ob das Bild zur linken (-90°) oder rechten (+90°) Seite der Fahrtrichtung
# aufgenommen werden soll. Der Mittelstreifen liegt für eine Richtungsfahrbahn
# i.d.R. links. Für Gegenrichtung müsste das umgekehrt werden — wird in
# osm_sampling.py pro Fahrtrichtung automatisch bestimmt.
MEDIAN_SIDE_OFFSET_DEG = -90

# --- Overpass API (OpenStreetMap) ---
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# --- Klassifikations-Klassen für das MVP ---
# Bewusst grob gehalten (siehe Diskussion) - Subtypen sind spätere Ausbaustufe.
CLASSES = [
    "betonschutzwand",
    "stahlschutzplanke",
    "seilruckhaltesystem",
    "kein_system",
    "nicht_erkennbar",  # z.B. verdeckt durch Verkehr, Bild fehlt, zu weit weg
]

# Pfad zu Referenzbildern für Few-Shot-Prompting.
# Erwartete Struktur: reference_images/<klasse>/*.jpg
REFERENCE_IMAGES_DIR = "reference_images"

# Claude-Modell für die Bildklassifikation
CLAUDE_MODEL = "claude-sonnet-4-6"
