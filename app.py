"""
Streamlit-Oberfläche für die Autobahn-Schutzeinrichtungs-Klassifikation.

Lokal starten:
    streamlit run app.py

Deployment: siehe README.md, Abschnitt "Deployment als Web-App".
"""

from __future__ import annotations

import time

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from config import CLASSES, GOOGLE_MAPS_API_KEY, ANTHROPIC_API_KEY, MEDIAN_SIDE_OFFSET_DEG
from osm_sampling import get_samples_for_segment
from streetview import get_median_view
from classify import classify_image

st.set_page_config(page_title="Autobahn-Schutzeinrichtungen", layout="wide")

CLASS_COLORS = {
    "betonschutzwand": "#7f7f7f",
    "stahlschutzplanke": "#1f77b4",
    "seilruckhaltesystem": "#2ca02c",
    "kein_system": "#bcbd22",
    "nicht_erkennbar": "#d62728",
}

DEFAULT_CENTER = [48.1351, 11.5820]  # München


def init_state():
    if "bbox" not in st.session_state:
        st.session_state.bbox = None  # (south, west, north, east)
    if "results" not in st.session_state:
        st.session_state.results = None  # pandas DataFrame


def draw_selection_map():
    """Karte zum Zeichnen einer Bounding Box (Rechteck) mit dem Draw-Plugin."""
    m = folium.Map(location=DEFAULT_CENTER, zoom_start=11, control_scale=True)
    from folium.plugins import Draw

    Draw(
        export=False,
        draw_options={
            "rectangle": True,
            "polygon": False,
            "circle": False,
            "circlemarker": False,
            "marker": False,
            "polyline": False,
        },
        edit_options={"edit": True},
    ).add_to(m)
    return st_folium(m, height=420, width=None, key="selection_map")


def bbox_from_draw_result(draw_result) -> tuple[float, float, float, float] | None:
    """Extrahiert (south, west, north, east) aus dem zuletzt gezeichneten Rechteck."""
    if not draw_result:
        return None
    features = None
    if draw_result.get("all_drawings"):
        features = draw_result["all_drawings"]
    if not features:
        return None
    last = features[-1]
    coords = last["geometry"]["coordinates"][0]  # Liste von [lon, lat]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return (min(lats), min(lons), max(lats), max(lons))


def run_pipeline(bbox, ref, sample_distance_m, limit, status_area, progress_bar):
    status_area.info("Lade Autobahn-Segmente aus OpenStreetMap ...")
    samples = get_samples_for_segment(bbox, ref=ref or None, sample_distance_m=sample_distance_m)
    if limit:
        samples = samples[:limit]

    if not samples:
        status_area.error(
            "Keine Sample-Punkte gefunden. Bounding Box und/oder --ref-Filter prüfen."
        )
        return None

    rows = []
    n = len(samples)
    for i, sp in enumerate(samples):
        status_area.info(f"Punkt {i + 1}/{n}  ({sp.lat:.5f}, {sp.lon:.5f}) ...")
        try:
            sv = get_median_view(sp.lat, sp.lon, sp.heading_deg, MEDIAN_SIDE_OFFSET_DEG)
        except Exception as e:
            rows.append(_error_row(sp, f"streetview_error: {e}"))
            progress_bar.progress((i + 1) / n)
            continue

        if sv.status != "OK" or sv.image_bytes is None:
            rows.append(_error_row(sp, f"no_pano: {sv.status}"))
            progress_bar.progress((i + 1) / n)
            continue

        try:
            result = classify_image(sv.image_bytes)
        except Exception as e:
            rows.append(_error_row(sp, f"classify_error: {e}"))
            progress_bar.progress((i + 1) / n)
            continue

        rows.append(
            {
                "seq_index": sp.seq_index,
                "lat": sp.lat,
                "lon": sp.lon,
                "heading_deg": round(sp.heading_deg, 1),
                "pano_id": sv.pano_id,
                "pano_date": sv.date,
                "klasse": result.klasse,
                "konfidenz": result.konfidenz,
                "begruendung": result.begruendung,
            }
        )
        progress_bar.progress((i + 1) / n)
        time.sleep(0.2)

    status_area.success(f"Fertig: {len(rows)} Punkte verarbeitet.")
    return pd.DataFrame(rows)


def _error_row(sp, note: str) -> dict:
    return {
        "seq_index": sp.seq_index,
        "lat": sp.lat,
        "lon": sp.lon,
        "heading_deg": round(sp.heading_deg, 1),
        "pano_id": None,
        "pano_date": None,
        "klasse": "nicht_erkennbar",
        "konfidenz": 0.0,
        "begruendung": note,
    }


def render_results_map(df: pd.DataFrame):
    center = [df["lat"].mean(), df["lon"].mean()]
    m = folium.Map(location=center, zoom_start=13, control_scale=True)
    for _, row in df.iterrows():
        color = CLASS_COLORS.get(row["klasse"], "#000000")
        popup = (
            f"<b>{row['klasse']}</b> (Konfidenz {row['konfidenz']:.2f})<br>"
            f"{row['begruendung']}<br>"
            f"<small>Pano-Datum: {row['pano_date']}</small>"
        )
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=6,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.85,
            popup=folium.Popup(popup, max_width=250),
        ).add_to(m)

    legend_html = (
        '<div style="position: fixed; bottom: 30px; left: 30px; z-index:9999; '
        'background:white; padding:10px; border:1px solid #999; border-radius:4px; font-size:13px;">'
        "<b>Legende</b><br>"
        + "".join(
            f'<span style="color:{c}">&#9679;</span> {k}<br>' for k, c in CLASS_COLORS.items()
        )
        + "</div>"
    )
    m.get_root().html.add_child(folium.Element(legend_html))
    st_folium(m, height=500, width=None, key="results_map")


def main():
    init_state()

    st.title("🛣️ Autobahn-Schutzeinrichtungen klassifizieren")
    st.caption(
        "MVP: klassifiziert per Google Street View + Claude Vision, welche Schutzeinrichtung "
        "am Mittelstreifen eines gewählten Autobahnabschnitts verbaut ist."
    )

    if not GOOGLE_MAPS_API_KEY or not ANTHROPIC_API_KEY:
        st.warning(
            "Es fehlen API-Keys. Lokal über Umgebungsvariablen setzen, oder in "
            "`.streamlit/secrets.toml` (siehe README) hinterlegen: "
            "`GOOGLE_MAPS_API_KEY`, `ANTHROPIC_API_KEY`."
        )

    with st.sidebar:
        st.header("Einstellungen")
        st.markdown("**1. Abschnitt wählen**  \nRechteck auf der Karte zeichnen.")
        ref = st.text_input('Autobahn-Ref (optional, z.B. "A9")', value="")
        sample_distance_m = st.slider("Sample-Abstand (m)", 25, 500, 100, step=25)
        limit = st.number_input(
            "Max. Punkte pro Lauf (Kosten-/Zeitlimit)", min_value=1, max_value=500, value=20
        )
        st.caption(
            "Tipp: für den ersten Testlauf niedrig halten - jeder Punkt kostet einen "
            "Street-View- und einen Claude-API-Call."
        )

    st.subheader("1. Streckenabschnitt auswählen")
    draw_result = draw_selection_map()
    bbox = bbox_from_draw_result(draw_result)

    if bbox:
        st.session_state.bbox = bbox
        south, west, north, east = bbox
        st.caption(f"Gewählte Bounding Box: south={south:.5f}, west={west:.5f}, north={north:.5f}, east={east:.5f}")
    elif st.session_state.bbox:
        bbox = st.session_state.bbox

    st.subheader("2. Klassifikation ausführen")
    run_disabled = bbox is None or not GOOGLE_MAPS_API_KEY or not ANTHROPIC_API_KEY
    if st.button("🚀 Klassifikation starten", disabled=run_disabled, type="primary"):
        status_area = st.empty()
        progress_bar = st.progress(0.0)
        df = run_pipeline(bbox, ref, sample_distance_m, int(limit), status_area, progress_bar)
        if df is not None:
            st.session_state.results = df

    if bbox is None:
        st.info("Zeichne zunächst ein Rechteck auf der Karte oben, um einen Abschnitt zu wählen.")

    if st.session_state.results is not None:
        df = st.session_state.results
        st.subheader("3. Ergebnisse")

        counts = df["klasse"].value_counts()
        cols = st.columns(len(CLASSES))
        for col, klasse in zip(cols, CLASSES):
            col.metric(klasse, int(counts.get(klasse, 0)))

        render_results_map(df)

        st.dataframe(df, use_container_width=True)
        st.download_button(
            "📥 Ergebnisse als CSV herunterladen",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="results.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
