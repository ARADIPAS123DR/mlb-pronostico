# =============================================================================
# MLB PRONÓSTICO ANALYZER — App Standalone
# Bullpen + Partidos del Día + Pronóstico de Ventaja por Partido
# =============================================================================

import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests as _req_http
import re
import unicodedata
from datetime import datetime, date, timedelta

try:
    from bs4 import BeautifulSoup as _BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    import pybaseball
    from pybaseball import statcast
    try:
        pybaseball.cache.enable()
    except Exception:
        pass
    # Parchear headers para evitar 403
    try:
        import requests as _requests
        import pybaseball.datasources.html_table_processor as _htp
        _BROWSER_HEADERS = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        _orig_get = _requests.get
        def _patched_get(url, **kwargs):
            headers = kwargs.pop("headers", {})
            headers = {**_BROWSER_HEADERS, **headers}
            return _orig_get(url, headers=headers, **kwargs)
        _htp.requests.get = _patched_get
    except Exception:
        pass
    HAS_PYBASEBALL = True
except ImportError:
    HAS_PYBASEBALL = False

# =============================================================================
# CONSTANTES
# =============================================================================

MLB_TEAMS = [
    "ARI", "ATL", "BAL", "BOS", "CHC", "CWS", "CIN", "CLE",
    "COL", "DET", "HOU", "KC",  "LAA", "LAD", "MIA", "MIL",
    "MIN", "NYM", "NYY", "OAK", "PHI", "PIT", "SD",  "SEA",
    "SF",  "STL", "TB",  "TEX", "TOR", "WSH",
]

TEAM_NAMES = {
    "ARI": "Arizona Diamondbacks",    "ATL": "Atlanta Braves",
    "BAL": "Baltimore Orioles",       "BOS": "Boston Red Sox",
    "CHC": "Chicago Cubs",            "CWS": "Chicago White Sox",
    "CIN": "Cincinnati Reds",         "CLE": "Cleveland Guardians",
    "COL": "Colorado Rockies",        "DET": "Detroit Tigers",
    "HOU": "Houston Astros",          "KC":  "Kansas City Royals",
    "LAA": "Los Angeles Angels",      "LAD": "Los Angeles Dodgers",
    "MIA": "Miami Marlins",           "MIL": "Milwaukee Brewers",
    "MIN": "Minnesota Twins",         "NYM": "New York Mets",
    "NYY": "New York Yankees",        "OAK": "Oakland Athletics",
    "PHI": "Philadelphia Phillies",   "PIT": "Pittsburgh Pirates",
    "SD":  "San Diego Padres",        "SEA": "Seattle Mariners",
    "SF":  "San Francisco Giants",    "STL": "St. Louis Cardinals",
    "TB":  "Tampa Bay Rays",          "TEX": "Texas Rangers",
    "TOR": "Toronto Blue Jays",       "WSH": "Washington Nationals",
}

# Statcast usa abreviaciones distintas para algunos equipos
STATCAST_ABBR = {
    "ARI": "AZ",   # Arizona Diamondbacks
    "OAK": "ATH",  # Sacramento Athletics 2025
}

FIP_CONST = 3.10

# Statcast abbr → internal abbr (reverse of STATCAST_ABBR)
SC_TO_INT = {"AZ": "ARI", "ATH": "OAK"}

# MLB Stats API team IDs
MLB_TEAM_IDS = {
    "ARI": 109, "ATL": 144, "BAL": 110, "BOS": 111,
    "CHC": 112, "CWS": 145, "CIN": 113, "CLE": 114,
    "COL": 115, "DET": 116, "HOU": 117, "KC":  118,
    "LAA": 108, "LAD": 119, "MIA": 146, "MIL": 158,
    "MIN": 142, "NYM": 121, "NYY": 147, "OAK": 133,
    "PHI": 143, "PIT": 134, "SD":  135, "SEA": 136,
    "SF":  137, "STL": 138, "TB":  139, "TEX": 140,
    "TOR": 141, "WSH": 120,
}

# MLB Stats API venue IDs (para clima)
MLB_VENUE_IDS = {
    "ARI": 15,  "ATL": 4705, "BAL": 2,   "BOS": 3,
    "CHC": 17,  "CWS": 4,   "CIN": 2602, "CLE": 5,
    "COL": 19,  "DET": 2394, "HOU": 2392,"KC":  7,
    "LAA": 1,   "LAD": 22,  "MIA": 4169, "MIL": 32,
    "MIN": 3312,"NYM": 3289, "NYY": 3313, "OAK": 10,
    "PHI": 2681,"PIT": 31,  "SD":  2680, "SEA": 680,
    "SF":  2395,"STL": 2889, "TB":  12,  "TEX": 5325,
    "TOR": 14,  "WSH": 3309,
}

# Coordenadas (lat, lon) de cada estadio para Open-Meteo
VENUE_COORDS = {
    "ARI": (33.4453, -112.0667), "ATL": (33.7350, -84.3900),
    "BAL": (39.2838, -76.6218),  "BOS": (42.3467, -71.0972),
    "CHC": (41.9484, -87.6553),  "CWS": (41.8300, -87.6338),
    "CIN": (39.0979, -84.5082),  "CLE": (41.4962, -81.6852),
    "COL": (39.7559, -104.9942), "DET": (42.3390, -83.0485),
    "HOU": (29.7572, -95.3555),  "KC":  (39.0517, -94.4803),
    "LAA": (33.8003, -117.8827), "LAD": (34.0739, -118.2400),
    "MIA": (25.7781, -80.2197),  "MIL": (43.0280, -87.9712),
    "MIN": (44.9817, -93.2778),  "NYM": (40.7571, -73.8458),
    "NYY": (40.8296, -73.9262),  "OAK": (37.7516, -122.2005),
    "PHI": (39.9061, -75.1665),  "PIT": (40.4469, -80.0057),
    "SD":  (32.7076, -117.1570), "SEA": (47.5914, -122.3325),
    "SF":  (37.7786, -122.3893), "STL": (38.6226, -90.1928),
    "TB":  (27.7682, -82.6534),  "TEX": (32.7473, -97.0822),
    "TOR": (43.6414, -79.3894),  "WSH": (38.8730, -77.0074),
}

# Orientación del estadio: ángulo en grados (Norte=0) de home plate → center field.
# Viento soplando EN ESTA DIRECCIÓN = "saliendo hacia CF".
STADIUM_CF_BEARING = {
    "ARI":  0,   # Chase Field — techo retráctil, viento mínimo
    "ATL":  7,   # Truist Park — apunta ~N
    "BAL": 30,   # Camden Yards — apunta ~NNE
    "BOS":  60,  # Fenway Park — apunta ~ENE
    "CHC":  58,  # Wrigley Field — apunta ~ENE
    "CWS": 330,  # Guaranteed Rate — apunta ~NNW
    "CIN":  25,  # Great American — apunta ~NNE
    "CLE": 320,  # Progressive Field — apunta ~NNW
    "COL": 292,  # Coors Field — apunta ~WNW
    "DET": 340,  # Comerica Park — apunta ~NNW
    "HOU": 230,  # Minute Maid Park — techo retráctil
    "KC":  15,   # Kauffman Stadium — apunta ~NNE
    "LAA": 265,  # Angel Stadium — apunta ~W
    "LAD": 330,  # Dodger Stadium — apunta ~NNW
    "MIA": 10,   # LoanDepot Park — techo retráctil
    "MIL": 310,  # American Family Field — techo retráctil
    "MIN": 350,  # Target Field — apunta ~N
    "NYM": 350,  # Citi Field — apunta ~N
    "NYY":  55,  # Yankee Stadium — apunta ~NE
    "OAK": 332,  # Oakland Coliseum — apunta ~NNW
    "PHI": 350,  # Citizens Bank Park — apunta ~N
    "PIT": 328,  # PNC Park — apunta ~NNW
    "SD":  315,  # Petco Park — apunta ~NW
    "SEA": 345,  # T-Mobile Park — apunta ~NNW
    "SF":  10,   # Oracle Park — apunta ~N
    "STL": 297,  # Busch Stadium — apunta ~WNW
    "TB":  17,   # Tropicana Field — domo, sin viento
    "TEX": 20,   # Globe Life Field — techo retráctil
    "TOR": 28,   # Rogers Centre — domo
    "WSH": 338,  # Nationals Park — apunta ~NNW
}

# Estadios techados/domo (sin efecto de viento)
DOMED_STADIUMS = {"ARI", "HOU", "MIA", "MIL", "TB", "TEX", "TOR"}

PA_EVENTS = {
    "strikeout", "walk", "hit_by_pitch", "single", "double", "triple", "home_run",
    "field_out", "force_out", "grounded_into_double_play", "double_play",
    "fielders_choice", "fielders_choice_out", "sac_fly", "sac_bunt", "catcher_interf",
}

# =============================================================================
# FUNCIONES DE DATOS
# =============================================================================

@st.cache_data(ttl=1800, show_spinner=False)
def cargar_statcast_global(dias: int = 14) -> pd.DataFrame:
    if not HAS_PYBASEBALL:
        return pd.DataFrame()
    try:
        end_dt   = date.today()
        start_dt = end_dt - timedelta(days=dias)
        # Descarga en bloques de 7 días para evitar recursión infinita de pybaseball
        CHUNK = 7
        chunks = []
        chunk_start = start_dt
        while chunk_start <= end_dt:
            chunk_end = min(chunk_start + timedelta(days=CHUNK - 1), end_dt)
            try:
                part = statcast(
                    chunk_start.strftime("%Y-%m-%d"),
                    chunk_end.strftime("%Y-%m-%d"),
                )
                if part is not None and not part.empty:
                    chunks.append(part)
            except Exception:
                pass
            chunk_start = chunk_end + timedelta(days=1)
        if not chunks:
            return pd.DataFrame()
        raw = pd.concat(chunks, ignore_index=True)
        raw["game_date"] = pd.to_datetime(raw["game_date"]).dt.date
        # Solo temporada regular (excluye pretemporada S, postemporada D/L/W/F)
        if "game_type" in raw.columns:
            raw = raw[raw["game_type"] == "R"].copy()
        if raw.empty:
            return pd.DataFrame()
        return raw
    except Exception as e:
        st.warning(f"Statcast error: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=1800, show_spinner=False)
def cargar_bullpen_equipo_solo(team: str, dias: int = 14) -> pd.DataFrame:
    """Descarga Statcast solo para un equipo (usado en la tab Bullpen individual)."""
    if not HAS_PYBASEBALL:
        return pd.DataFrame()
    try:
        end_dt   = date.today()
        start_dt = end_dt - timedelta(days=dias)
        raw = statcast(start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))
        if raw is None or raw.empty:
            return pd.DataFrame()
        raw["game_date"] = pd.to_datetime(raw["game_date"]).dt.date
        return _extraer_apariciones_equipo(raw, team)
    except Exception:
        return pd.DataFrame()


def _extraer_apariciones_equipo(raw: pd.DataFrame, team: str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    sc_team = STATCAST_ABBR.get(team, team)
    mask = (
        ((raw["home_team"] == sc_team) & (raw["inning_topbot"] == "Top")) |
        ((raw["away_team"] == sc_team) & (raw["inning_topbot"] == "Bot"))
    )
    df = raw[mask].copy()
    if df.empty:
        return pd.DataFrame()

    # Excluir starters (primer pitcher del inning 1 por juego)
    df_inn1 = df[df["inning"] == 1]
    starter_ids = set(
        df_inn1.sort_values("at_bat_number")
        .groupby(["game_date", "game_pk"])["pitcher"]
        .first().dropna()
    )
    df = df[~df["pitcher"].isin(starter_ids)].copy()
    if df.empty:
        return pd.DataFrame()

    records = []
    for (pid, gdate, gpk), grp in df.groupby(["pitcher", "game_date", "game_pk"]):
        events = grp["events"].dropna()
        pa  = int(events.isin(PA_EVENTS).sum())
        k   = int((events == "strikeout").sum())
        bb  = int(events.isin({"walk", "hit_by_pitch"}).sum())
        h   = int(events.isin({"single", "double", "triple", "home_run"}).sum())
        hr  = int((events == "home_run").sum())
        go_fo = int(events.isin({"field_out","force_out","grounded_into_double_play",
                                  "double_play","fielders_choice_out","sac_fly","sac_bunt"}).sum())
        ip  = round((k + go_fo) / 3, 1)
        er  = 0
        if "post_bat_score" in grp.columns and "bat_score" in grp.columns:
            er = int((grp["post_bat_score"].fillna(0) - grp["bat_score"].fillna(0)).clip(lower=0).sum())
        woba_sum = float(grp["woba_value"].fillna(0).sum()) if "woba_value" in grp.columns else 0.0
        name_col = next((nc for nc in ["player_name", "pitcher_name"] if nc in grp.columns), None)
        pname = grp[name_col].iloc[0] if name_col else str(pid)
        records.append({
            "team": team, "pitcher_id": pid, "pitcher_name": pname,
            "game_date": gdate, "game_pk": gpk,
            "pitches": len(grp), "PA": pa, "IP": ip,
            "K": k, "BB": bb, "H": h, "HR": hr, "ER": er, "woba_sum": woba_sum,
        })
    return pd.DataFrame(records) if records else pd.DataFrame()


def _filtrar_calificados(df_apps: pd.DataFrame, min_juegos: int = 2) -> pd.DataFrame:
    """Conserva solo pitchers con >= min_juegos apariciones (game_pk distintos)."""
    if df_apps.empty:
        return df_apps
    juegos = df_apps.groupby("pitcher_id")["game_pk"].nunique()
    ids_ok = juegos[juegos >= min_juegos].index
    return df_apps[df_apps["pitcher_id"].isin(ids_ok)].copy()


def _calcular_stats(df_apps: pd.DataFrame) -> pd.DataFrame:
    df_apps = _filtrar_calificados(df_apps)
    rows = []
    for pid, grp in df_apps.groupby("pitcher_id"):
        name = grp["pitcher_name"].iloc[0]
        tp = grp["PA"].sum(); ti = grp["IP"].sum()
        tk = grp["K"].sum();  tb = grp["BB"].sum()
        th = grp["H"].sum();  thr = grp["HR"].sum()
        ter = grp["ER"].sum(); tw = grp["woba_sum"].sum()
        rows.append({
            "ID":      pid,
            "Pitcher": name,
            "G":       len(grp),
            "IP":      round(ti, 2),
            "PA":      int(tp),
            "K%":      round(tk / tp * 100, 2) if tp > 0 else 0.0,
            "BB%":     round(tb / tp * 100, 2) if tp > 0 else 0.0,
            "FIP":     round(max(0.0, (13*thr + 3*tb - 2*tk) / ti + FIP_CONST), 2) if ti > 0 else 4.50,
            "ERA":     round(ter / ti * 9, 2) if ti > 0 else 0.0,
            "WHIP":    round((th + tb) / ti, 2) if ti > 0 else 0.0,
            "wOBA":    round(tw / tp, 2) if tp > 0 else 0.30,
            "ER":      int(ter),
            "Pitches": int(grp["pitches"].sum()),
        })
    return pd.DataFrame(rows).sort_values("FIP") if rows else pd.DataFrame()


def _disponibilidad(df_apps: pd.DataFrame, fecha: date) -> pd.DataFrame:
    d1 = fecha - timedelta(days=1)
    d2 = fecha - timedelta(days=2)
    rows = []
    for pid, grp in df_apps.groupby("pitcher_id"):
        name   = grp["pitcher_name"].iloc[0]
        dates  = set(grp["game_date"])
        pit_d1 = d1 in dates; pit_d2 = d2 in dates
        p_d1   = int(grp[grp["game_date"] == d1]["pitches"].sum()) if pit_d1 else 0
        p_d2   = int(grp[grp["game_date"] == d2]["pitches"].sum()) if pit_d2 else 0
        dias_ult = (fecha - max(dates)).days if dates else None

        if (pit_d1 and pit_d2) or (pit_d1 and p_d1 > 30):
            estado = "❌ No disponible"
            razon  = f"2 días seguidos o ayer {p_d1}p"
        elif pit_d1 and p_d1 > 14:
            estado = "⚠️ Limitado"
            razon  = f"Lanzó ayer: {p_d1}p"
        elif pit_d2 and p_d2 > 40:
            estado = "⚠️ Limitado"
            razon  = f"Lanzó hace 2d: {p_d2}p"
        elif dias_ult is not None and dias_ult >= 4:
            estado = "🟢 Fresco"
            razon  = f"Último uso: hace {dias_ult}d"
        else:
            estado = "🟢 Disponible"
            razon  = f"Último uso: hace {dias_ult if dias_ult is not None else '?'}d"

        rows.append({
            "ID": pid, "Pitcher": name, "Disponib.": estado, "Razón": razon,
            "Lanzó D-1": f"{p_d1}p" if pit_d1 else "—",
            "Lanzó D-2": f"{p_d2}p" if pit_d2 else "—",
            "Días desc.": dias_ult if dias_ult is not None else "—",
        })
    return pd.DataFrame(rows)


def _ids_disponibles(df_apps: pd.DataFrame, fecha: date) -> set:
    d1 = fecha - timedelta(days=1)
    d2 = fecha - timedelta(days=2)
    ids = set()
    for pid, grp in df_apps.groupby("pitcher_id"):
        dates = set(grp["game_date"])
        pit_d1 = d1 in dates; pit_d2 = d2 in dates
        p_d1   = int(grp[grp["game_date"] == d1]["pitches"].sum()) if pit_d1 else 0
        p_d2   = int(grp[grp["game_date"] == d2]["pitches"].sum()) if pit_d2 else 0
        if (pit_d1 and pit_d2) or (pit_d1 and p_d1 > 30):
            pass  # no disponible
        else:
            ids.add(pid)
    return ids


def _stats_agregadas(df: pd.DataFrame) -> dict:
    """Calcula FIP, K%, BB%, wOBA, WHIP agregados de un DataFrame de apariciones."""
    tp = df["PA"].sum(); ti = df["IP"].sum()
    tk = df["K"].sum();  tb = df["BB"].sum()
    th = df["H"].sum();  thr = df["HR"].sum()
    ter = df["ER"].sum(); tw = df["woba_sum"].sum()
    return {
        "K%":   round(tk / tp * 100, 1) if tp > 0 else 0.0,
        "BB%":  round(tb / tp * 100, 1) if tp > 0 else 0.0,
        "FIP":  round(max(0.0, (13*thr + 3*tb - 2*tk) / ti + FIP_CONST), 2) if ti > 0 else 9.99,
        "WHIP": round((th + tb) / ti, 2) if ti > 0 else 9.99,
        "wOBA": round(tw / tp, 3) if tp > 0 else 0.999,
        "ER/9": round(ter / ti * 9, 2) if ti > 0 else 0.0,
        "IP":   round(ti, 1),
    }


# =============================================================================
# FUNCIÓN: Saves y Holds — temporada (MLB Stats API)
# =============================================================================

@st.cache_data(ttl=3600, show_spinner=False)
def get_saves_holds_season() -> pd.DataFrame:
    """Descarga saves y holds de la temporada desde el MLB Stats API."""
    season = date.today().year
    url = (
        "https://statsapi.mlb.com/api/v1/stats"
        f"?stats=season&group=pitching&season={season}"
        "&sportId=1&playerPool=All&limit=3000"
    )
    try:
        r = _req_http.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        splits = (data.get("stats") or [{}])[0].get("splits", [])
        rows = []
        for split in splits:
            stat        = split.get("stat", {})
            team_info   = split.get("team", {})
            player_info = split.get("player", {})
            team_abbr   = team_info.get("abbreviation", "")
            team_abbr   = SC_TO_INT.get(team_abbr, team_abbr)
            rows.append({
                "pitcher_id":   player_info.get("id"),
                "pitcher_name": player_info.get("fullName", ""),
                "team":         team_abbr,
                "SV":           int(stat.get("saves", 0) or 0),
                "HLD":          int(stat.get("holds", 0) or 0),
                "SVO":          int(stat.get("saveOpportunities", 0) or 0),
            })
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


# =============================================================================
# TAB 1: BULLPEN INDIVIDUAL
# =============================================================================

def tab_bullpen_individual():
    st.markdown("## Análisis de Bullpen — Equipo Individual")

    col1, col2, col3 = st.columns(3)
    with col1:
        team = st.selectbox("Equipo", MLB_TEAMS,
                            format_func=lambda t: f"{t} — {TEAM_NAMES.get(t, t)}",
                            key="ind_team")
    with col2:
        fecha = st.date_input("Fecha del partido", value=date.today(), key="ind_fecha")
    with col3:
        st.markdown(" ")

    nombre = TEAM_NAMES.get(team, team)
    st.markdown(f"### {nombre} — Bullpen últimas 2 semanas")

    with st.spinner(f"Cargando datos de {team}..."):
        raw_global = cargar_statcast_global(dias=14)
        df_apps = _extraer_apariciones_equipo(raw_global, team) if not raw_global.empty else pd.DataFrame()

    if df_apps.empty:
        st.warning(f"Sin datos Statcast para {nombre} en los últimos 14 días.")
        return

    n_rel = df_apps["pitcher_id"].nunique()
    fecha_rng = f"{df_apps['game_date'].min()} → {df_apps['game_date'].max()}"
    st.caption(f"Relevistas: **{n_rel}** | Rango: {fecha_rng}")

    # ── Stats completas ───────────────────────────────────────────────────────
    st.markdown("#### Stats últimas 2 semanas — todos los relevistas")
    st.caption("Solo aparecen relevistas con **≥ 2 apariciones** en el período (mín. 2 juegos distintos).")
    stats = _calcular_stats(df_apps)

    def _color_fip(val):
        try:
            v = float(val)
            if v < 3.50:   return "background-color:#d4edda;color:#155724"
            elif v < 4.50: return "background-color:#fff3cd;color:#856404"
            else:           return "background-color:#f8d7da;color:#721c24"
        except:
            return ""

    if not stats.empty:
        _num_cols = ["IP","K%","BB%","FIP","ERA","WHIP","wOBA"]
        st.dataframe(
            stats[["Pitcher","G","IP","PA","K%","BB%","FIP","ERA","WHIP","wOBA","ER"]]
            .set_index("Pitcher")
            .round({c: 2 for c in _num_cols})
            .style.map(_color_fip, subset=["FIP"]),
            use_container_width=True,
        )

    # ── Disponibilidad ────────────────────────────────────────────────────────
    st.markdown(f"#### Disponibilidad — {fecha.strftime('%d %b %Y')}")
    disp_df = _disponibilidad(df_apps, fecha)
    ids_disp = _ids_disponibles(df_apps, fecha)
    ids_no   = set(df_apps["pitcher_id"].unique()) - ids_disp

    c1, c2, c3 = st.columns(3)
    disp_rows = disp_df[disp_df["Disponib."].str.contains("🟢")]
    lim_rows  = disp_df[disp_df["Disponib."].str.contains("⚠️")]
    no_rows   = disp_df[disp_df["Disponib."].str.contains("❌")]
    c1.metric("🟢 Disponibles",    len(disp_rows))
    c2.metric("⚠️ Limitados",      len(lim_rows))
    c3.metric("❌ No disponibles", len(no_rows))

    if not disp_df.empty:
        st.dataframe(disp_df.drop(columns=["ID"]).set_index("Pitcher"), use_container_width=True)

    # ── Comparación disponible vs completo ────────────────────────────────────
    st.markdown("#### Comparación: disponibles vs bullpen completo")
    df_disp_apps = df_apps[df_apps["pitcher_id"].isin(ids_disp)]

    if not df_disp_apps.empty and not df_apps.empty:
        s_comp = _stats_agregadas(df_apps)
        s_disp = _stats_agregadas(df_disp_apps)
        cmp = []
        for m in ["FIP", "K%", "BB%", "WHIP", "wOBA"]:
            vc, vd = s_comp.get(m, 0), s_disp.get(m, 0)
            delta = vd - vc
            mejor_mas_alto = m == "K%"
            if mejor_mas_alto:
                icono = "🔴 Debilitado" if delta < -2 else ("🟢 Reforzado" if delta > 2 else "➡️ Similar")
            else:
                icono = "🔴 Debilitado" if delta > 0.3 else ("🟢 Reforzado" if delta < -0.3 else "➡️ Similar")
            cmp.append({"Métrica": m, "Completo": round(vc, 3),
                         "Disponibles": round(vd, 3), "Δ": f"{delta:+.3f}", "Estado": icono})
        st.dataframe(pd.DataFrame(cmp).set_index("Métrica").round({"Completo": 2, "Disponibles": 2}), use_container_width=True)

        debil = sum(1 for r in cmp if "Debilitado" in r["Estado"])
        pct_no = len(ids_no) / max(n_rel, 1) * 100
        if debil >= 2 or pct_no > 40:
            st.error(f"⚠️ DESVENTAJA DE BULLPEN — {debil} métricas debilitadas, {pct_no:.0f}% no disponibles.")
        else:
            st.success(f"✅ Bullpen disponible en buenas condiciones ({100-pct_no:.0f}% disponible).")

    # ── Pitchers clave no disponibles ─────────────────────────────────────────
    if ids_no and not stats.empty:
        nd_stats = stats[stats["ID"].isin(ids_no)]
        if not nd_stats.empty:
            st.markdown("##### No disponibles hoy:")
            st.dataframe(
                nd_stats[["Pitcher","FIP","K%","BB%","WHIP"]].sort_values("FIP").set_index("Pitcher"),
                use_container_width=True,
            )

    # ── Tendencia FIP — últimos 45 días ───────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📈 Tendencia FIP del Bullpen — últimos 45 días")
    st.caption("FIP diario calculado con todas las apariciones del bullpen en cada fecha. Línea suavizada = promedio móvil 5 días.")

    with st.spinner("Cargando 45 días para tendencia FIP..."):
        raw_45d = cargar_statcast_global(dias=45)
        df_apps_45 = _extraer_apariciones_equipo(raw_45d, team) if not raw_45d.empty else pd.DataFrame()

    if not df_apps_45.empty:
        # Calcular FIP por día (todas las apariciones de ese día)
        _daily_fips = []
        for _gdate, _grp_day in df_apps_45.groupby("game_date"):
            _ti = _grp_day["IP"].sum()
            if _ti <= 0:
                continue
            _tk = _grp_day["K"].sum()
            _tb = _grp_day["BB"].sum()
            _thr = _grp_day["HR"].sum()
            _fip_day = round(max(0.0, (13*_thr + 3*_tb - 2*_tk) / _ti + FIP_CONST), 2)
            _daily_fips.append({"Fecha": _gdate, "FIP": _fip_day})

        if len(_daily_fips) >= 2:
            _df_trend = (pd.DataFrame(_daily_fips)
                         .sort_values("Fecha")
                         .reset_index(drop=True))
            # Promedio móvil 5 días (o menos si hay pocas fechas)
            _win = min(5, len(_df_trend))
            _df_trend["FIP_suav"] = (_df_trend["FIP"]
                                     .rolling(window=_win, min_periods=1)
                                     .mean()
                                     .round(2))

            _fig_trend = go.Figure()
            # Puntos diarios (semitransparentes)
            _fig_trend.add_trace(go.Scatter(
                x=_df_trend["Fecha"],
                y=_df_trend["FIP"],
                mode="markers",
                name="FIP diario",
                marker=dict(color="#1f77b4", size=7, opacity=0.55),
                hovertemplate="<b>%{x}</b><br>FIP: %{y}<extra></extra>",
            ))
            # Línea suavizada
            _fig_trend.add_trace(go.Scatter(
                x=_df_trend["Fecha"],
                y=_df_trend["FIP_suav"],
                mode="lines",
                name=f"Prom. móvil {_win}d",
                line=dict(color="#ff7f0e", width=2.5),
                hovertemplate="<b>%{x}</b><br>Prom. móvil: %{y}<extra></extra>",
            ))
            # Líneas de referencia
            _x_rng = [_df_trend["Fecha"].min(), _df_trend["Fecha"].max()]
            _fig_trend.add_shape(type="line", x0=_x_rng[0], x1=_x_rng[1],
                                 y0=3.50, y1=3.50,
                                 line=dict(color="#28a745", dash="dash", width=1.5))
            _fig_trend.add_shape(type="line", x0=_x_rng[0], x1=_x_rng[1],
                                 y0=4.50, y1=4.50,
                                 line=dict(color="#dc3545", dash="dash", width=1.5))
            _fig_trend.add_annotation(x=_x_rng[1], y=3.50, text="Elite (3.50)",
                                      showarrow=False, xanchor="right",
                                      font=dict(color="#28a745", size=11))
            _fig_trend.add_annotation(x=_x_rng[1], y=4.50, text="Malo (4.50)",
                                      showarrow=False, xanchor="right",
                                      font=dict(color="#dc3545", size=11))
            _fig_trend.update_layout(
                height=360,
                xaxis=dict(
                    title="Fecha",
                    tickformat="%d %b",   # "29 Mar" — sin horas
                    dtick="86400000",     # un tick por día (ms)
                    tickangle=-45,
                ),
                yaxis=dict(title="FIP", autorange=True),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=20, b=60, l=50, r=20),
                legend=dict(orientation="h", y=1.08),
            )
            st.plotly_chart(_fig_trend, use_container_width=True)
        else:
            st.info("Datos insuficientes para graficar tendencia (menos de 2 fechas con actividad).")
    else:
        st.info(f"Sin datos Statcast de 45 días para {nombre}.")


# =============================================================================
# TAB 2: BULLPEN LIGA
# =============================================================================

def tab_bullpen_liga():
    st.markdown("## Liga — Dashboard de Bullpens (30 equipos)")

    col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns([1, 1, 1, 1, 1])
    with col_f1:
        fecha = st.date_input("Fecha para disponibilidad", value=date.today(), key="liga_fecha")
    with col_f2:
        metrica_ord = st.selectbox("Ordenar por",
                                   ["FIP", "WHIP", "wOBA", "K%", "BB%", "ER/9", "Disp%"],
                                   key="liga_orden")
    with col_f3:
        equipo31 = st.selectbox("Equipo 31 (disponibles)",
                                ["— Ninguno —"] + MLB_TEAMS,
                                key="liga_eq31",
                                help="Inserta los pitchers disponibles de este equipo como posición 31")
    with col_f4:
        vista_tabla = st.selectbox("Vista de tabla",
                                   ["Tabla completa", "Solo disponibles"],
                                   key="liga_vista",
                                   help="Tabla completa: stats del bullpen total. Solo disponibles: stats calculadas solo con pitchers disponibles hoy.")
    with col_f5:
        st.markdown(" ")
        st.button("Actualizar datos", type="primary", key="liga_btn")

    st.caption("Una sola descarga de Statcast cubre los 16 últimos días para todos los equipos. Cache 30 min.")

    with st.spinner("Descargando Statcast (todos los equipos, últimos 16 días)..."):
        raw_global = cargar_statcast_global(dias=16)

    if raw_global.empty:
        st.error("No se pudo cargar Statcast. Verifica conexión.")
        return

    d1 = fecha - timedelta(days=1)
    d2 = fecha - timedelta(days=2)

    filas = []
    progress = st.progress(0, text="Procesando equipos...")
    for i, team in enumerate(MLB_TEAMS):
        progress.progress((i + 1) / len(MLB_TEAMS), text=f"Procesando {team}...")
        df_t = _extraer_apariciones_equipo(raw_global, team)

        _fila_vacia = {
            "Team": team, "Nombre": TEAM_NAMES.get(team, team),
            "IP": 0, "K%": 0, "BB%": 0, "FIP": 0,
            "WHIP": 0, "wOBA": 0, "ER/9": 0, "Relev.": 0,
            "Disp": 0, "Limit": 0, "NDisp": 0, "Disp%": 0,
            "FIP_disp": 0, "K%_disp": 0, "BB%_disp": 0, "wOBA_disp": 0,
            "_sin_datos": True,
        }
        if df_t.empty:
            filas.append(_fila_vacia)
            continue

        df_t = _filtrar_calificados(df_t, min_juegos=1)   # inicio de temporada: 1 aparición basta
        if df_t.empty:
            filas.append(_fila_vacia)
            continue
        s = _stats_agregadas(df_t)
        n_rel = df_t["pitcher_id"].nunique()

        # Disponibilidad
        n_disp = n_limit = n_no = 0
        ids_disponibles = set()
        for pid, grp_p in df_t.groupby("pitcher_id"):
            dates_p = set(grp_p["game_date"])
            pit_d1  = d1 in dates_p; pit_d2 = d2 in dates_p
            p_d1 = int(grp_p[grp_p["game_date"] == d1]["pitches"].sum()) if pit_d1 else 0
            p_d2 = int(grp_p[grp_p["game_date"] == d2]["pitches"].sum()) if pit_d2 else 0
            if (pit_d1 and pit_d2) or (pit_d1 and p_d1 > 30):
                n_no += 1
            elif (pit_d1 and p_d1 > 14) or (pit_d2 and p_d2 > 40):
                n_limit += 1
                ids_disponibles.add(pid)
            else:
                n_disp += 1
                ids_disponibles.add(pid)

        disp_pct = round((n_disp + n_limit * 0.5) / max(n_rel, 1) * 100, 0)

        # Stats disponibles
        df_disp = df_t[df_t["pitcher_id"].isin(ids_disponibles)]
        if not df_disp.empty and df_disp["IP"].sum() > 0:
            sd = _stats_agregadas(df_disp)
            fip_d = sd["FIP"]; k_d = sd["K%"]; bb_d = sd["BB%"]; woba_d = sd["wOBA"]
        else:
            fip_d = s["FIP"]; k_d = s["K%"]; bb_d = s["BB%"]; woba_d = s["wOBA"]

        filas.append({
            "Team": team, "Nombre": TEAM_NAMES.get(team, team), "Relev.": n_rel,
            "IP": s["IP"], "K%": s["K%"], "BB%": s["BB%"], "FIP": s["FIP"],
            "WHIP": s["WHIP"], "wOBA": s["wOBA"], "ER/9": s["ER/9"],
            "Disp": n_disp, "Limit": n_limit, "NDisp": n_no, "Disp%": int(disp_pct),
            "FIP_disp": fip_d, "K%_disp": k_d, "BB%_disp": bb_d, "wOBA_disp": woba_d,
            "_sin_datos": False,
        })

    progress.empty()

    df_liga = pd.DataFrame(filas)
    if "_sin_datos" not in df_liga.columns:
        df_liga["_sin_datos"] = False
    df_liga["_sin_datos"] = df_liga["_sin_datos"].fillna(False)
    # Equipos sin datos siempre al fondo; los con datos se ordenan normalmente
    asc = metrica_ord not in ("K%", "Disp%")
    df_con  = df_liga[~df_liga["_sin_datos"]].sort_values(metrica_ord, ascending=asc)
    df_sin  = df_liga[df_liga["_sin_datos"]]
    df_liga = pd.concat([df_con, df_sin], ignore_index=True)

    # ── Equipo 31 ─────────────────────────────────────────────────────────────
    rank_eq31 = rank_completo = None
    if equipo31 != "— Ninguno —":
        df_t31 = _extraer_apariciones_equipo(raw_global, equipo31)
        if not df_t31.empty:
            ids_d31 = _ids_disponibles(df_t31, fecha)
            df_d31  = df_t31[df_t31["pitcher_id"].isin(ids_d31)]
            if not df_d31.empty:
                sd31 = _stats_agregadas(df_d31)
                nr31 = df_d31["pitcher_id"].nunique()
                nnd31 = df_t31["pitcher_id"].nunique() - nr31
                dp31 = round(nr31 / max(df_t31["pitcher_id"].nunique(), 1) * 100, 0)

                row31 = {
                    "Team": "EQ31",
                    "Nombre": f"★ {TEAM_NAMES.get(equipo31, equipo31)} DISPONIBLES",
                    "Relev.": nr31, "IP": sd31["IP"],
                    "K%": sd31["K%"], "BB%": sd31["BB%"], "FIP": sd31["FIP"],
                    "WHIP": sd31["WHIP"], "wOBA": sd31["wOBA"], "ER/9": sd31["ER/9"],
                    "Disp": nr31, "Limit": 0, "NDisp": nnd31, "Disp%": int(dp31),
                    "FIP_disp": sd31["FIP"], "K%_disp": sd31["K%"],
                    "BB%_disp": sd31["BB%"], "wOBA_disp": sd31["wOBA"],
                }

                rc = df_liga[df_liga["Team"] == equipo31]
                rank_completo = int(rc.index[0]) + 1 if not rc.empty else None

                df_liga = pd.concat([df_liga, pd.DataFrame([row31])], ignore_index=True)
                df_liga = df_liga.sort_values(metrica_ord, ascending=asc).reset_index(drop=True)
                rank_eq31  = int(df_liga[df_liga["Team"] == "EQ31"].index[0]) + 1
                total31    = len(df_liga)
                nombre_eq  = TEAM_NAMES.get(equipo31, equipo31)
                delta_pos  = rank_eq31 - (rank_completo or rank_eq31)

                st.divider()
                cv1, cv2, cv3 = st.columns(3)
                cv1.metric("Bullpen completo",  f"#{rank_completo or '?'} de 30")
                cv2.metric("Disponibles hoy",   f"#{rank_eq31} de {total31}",
                           delta=f"{-delta_pos:+d} pos" if rank_completo else None)
                cv3.metric("Pitchers disp.",    f"{nr31} de {df_t31['pitcher_id'].nunique()}")

                if rank_eq31 <= 5:
                    st.success(f"✅ {nombre_eq} DISPONIBLES → #{rank_eq31}/{total31} — Elite.")
                elif rank_eq31 <= total31 // 2:
                    st.info(f"➡️ {nombre_eq} DISPONIBLES → #{rank_eq31}/{total31} — Sobre la media.")
                elif rank_eq31 <= total31 - 5:
                    st.warning(f"⚠️ {nombre_eq} DISPONIBLES → #{rank_eq31}/{total31} — Bajo la media.")
                else:
                    st.error(f"🔴 {nombre_eq} DISPONIBLES → #{rank_eq31}/{total31} — Bottom 5. Desventaja severa.")

                if delta_pos > 5:
                    st.error(f"Caída de {delta_pos} posiciones — los mejores relevistas no están disponibles.")
                elif delta_pos > 0:
                    st.warning(f"Baja {delta_pos} posición(es) con solo los disponibles.")
                elif delta_pos < 0:
                    st.success(f"Sube {abs(delta_pos)} posición(es) — los pitchers frescos son mejores que el promedio.")

    df_liga["Rank"] = [
        str(i + 1) + ("★" if r == "EQ31" else "")
        for i, r in enumerate(df_liga["Team"])
    ]

    # ── Métricas resumen ──────────────────────────────────────────────────────
    df_30 = df_liga[(df_liga["Team"] != "EQ31") & (df_liga["IP"] > 0)]
    top3 = df_30.head(3)["Nombre"].tolist()
    bot3 = df_30.tail(3)["Nombre"].tolist()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Mejor bullpen (FIP)", top3[0] if top3 else "—")
    m2.metric("2do mejor",           top3[1] if len(top3) > 1 else "—")
    m3.metric("Peor bullpen (FIP)",  bot3[-1] if bot3 else "—")
    m4.metric("Disp% promedio liga", f"{int(df_30['Disp%'].mean())}%")

    # ── Tabla ─────────────────────────────────────────────────────────────────
    _fmt2 = st.column_config.NumberColumn(format="%.2f")
    _fmt1 = st.column_config.NumberColumn(format="%.1f")
    _fmt0 = st.column_config.NumberColumn(format="%d")

    if vista_tabla == "Solo disponibles":
        st.markdown("### Tabla — Solo pitchers disponibles")

        def _color_row_disp(row):
            if row.get("Team") == "EQ31":
                return ["background-color:#cce5ff;font-weight:bold"] * len(row)
            try:
                fip = float(row.get("FIP_disp", 5.0))
            except:
                fip = 5.0
            if row.get("_sin_datos", False):
                return ["background-color:#f0f0f0;color:#999999"] * len(row)
            bg = "#d4edda" if fip < 3.50 else ("#fff3cd" if fip < 4.20 else "#f8d7da")
            return [f"background-color:{bg}"] * len(row)

        cols_disp = ["Rank", "Team", "Nombre", "Relev.", "Disp", "Limit", "NDisp", "Disp%",
                     "FIP_disp", "K%_disp", "BB%_disp", "wOBA_disp"]
        _rc_disp = {c: 2 for c in ["FIP_disp","K%_disp","BB%_disp","wOBA_disp"] if c in df_liga.columns}
        df_show_disp = (df_liga[[c for c in cols_disp if c in df_liga.columns]]
                        .rename(columns={
                            "FIP_disp": "FIP (disp)", "K%_disp": "K% (disp)",
                            "BB%_disp": "BB% (disp)", "wOBA_disp": "wOBA (disp)",
                        })
                        .set_index(["Rank", "Nombre"])
                        .round({c: 2 for c in ["FIP (disp)","K% (disp)","BB% (disp)","wOBA (disp)"]}))
        st.dataframe(
            df_show_disp.style.apply(_color_row_disp, axis=1),
            use_container_width=True, height=950,
            column_config={
                "Team":        None,
                "FIP (disp)":  _fmt2,
                "K% (disp)":   _fmt1,
                "BB% (disp)":  _fmt1,
                "wOBA (disp)": _fmt2,
                "Disp":  _fmt0,
                "Limit": _fmt0,
                "NDisp": _fmt0,
                "Disp%": _fmt0,
            },
        )
        st.caption("★=Equipo 31 | Stats calculadas con pitchers disponibles hoy | 🟢 FIP<3.50 | 🟡 3.50-4.20 | 🔴 >4.20")

    else:
        st.markdown("### Tabla completa")

        def _color_row(row):
            if row.get("Team") == "EQ31":
                return ["background-color:#cce5ff;font-weight:bold"] * len(row)
            try:
                fip = float(row.get("FIP", 5.0))
            except:
                fip = 5.0
            if row.get("_sin_datos", False):
                return ["background-color:#f0f0f0;color:#999999"] * len(row)
            bg = "#d4edda" if fip < 3.50 else ("#fff3cd" if fip < 4.20 else "#f8d7da")
            return [f"background-color:{bg}"] * len(row)

        cols_show = ["Rank", "Team", "Nombre", "Relev.", "IP", "K%", "BB%", "FIP",
                     "WHIP", "wOBA", "ER/9", "Disp", "Limit", "NDisp", "Disp%"]
        _rc2_main = {c: 2 for c in ["IP","K%","BB%","FIP","WHIP","wOBA","ER/9"] if c in df_liga.columns}
        df_show = (df_liga[[c for c in cols_show if c in df_liga.columns]]
                   .set_index(["Rank", "Nombre"])
                   .round(_rc2_main))
        st.dataframe(
            df_show.style.apply(_color_row, axis=1),
            use_container_width=True, height=950,
            column_config={
                "Team":  None,
                "IP":    _fmt1,
                "K%":    _fmt1,
                "BB%":   _fmt1,
                "FIP":   _fmt2,
                "WHIP":  _fmt2,
                "wOBA":  _fmt2,
                "ER/9":  _fmt2,
                "Disp":  _fmt0,
                "Limit": _fmt0,
                "NDisp": _fmt0,
                "Disp%": _fmt0,
            },
        )
        st.caption("★=Equipo 31 | 🟢 FIP<3.50 | 🟡 3.50-4.20 | 🔴 >4.20")

    # ── Ranking disponibles ───────────────────────────────────────────────────
    st.markdown(f"#### Ranking — Mejores bullpens disponibles el {fecha.strftime('%d %b %Y')}")
    df_dr = df_liga[(df_liga["Team"] != "EQ31") & (~df_liga.get("_sin_datos", pd.Series(False, index=df_liga.index)))].copy()
    df_dr = df_dr[df_dr["IP"] > 0].sort_values("FIP_disp").reset_index(drop=True)
    df_dr["Rank_disp"] = range(1, len(df_dr) + 1)
    colores_dr = ["#28a745" if v < 3.50 else ("#ffc107" if v < 4.20 else "#dc3545")
                  for v in df_dr["FIP_disp"]]
    fig_rd = go.Figure(go.Bar(
        x=df_dr["Nombre"], y=df_dr["FIP_disp"], marker_color=colores_dr,
        text=[f"#{r} — {f}" for r, f in zip(df_dr["Rank_disp"], df_dr["FIP_disp"])],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>FIP disp: %{y}<br>K%%: %{customdata[0]} | BB%%: %{customdata[1]}<extra></extra>",
        customdata=df_dr[["K%_disp", "BB%_disp"]].values,
    ))
    fig_rd.update_layout(
        height=430, xaxis_tickangle=-45, yaxis_title="FIP (disponibles)",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=40, b=130),
        shapes=[
            dict(type="line", x0=-0.5, x1=len(df_dr)-0.5, y0=3.50, y1=3.50,
                 line=dict(color="#28a745", dash="dash", width=1.5)),
            dict(type="line", x0=-0.5, x1=len(df_dr)-0.5, y0=4.20, y1=4.20,
                 line=dict(color="#dc3545", dash="dash", width=1.5)),
        ],
    )
    st.plotly_chart(fig_rd, use_container_width=True)

    # ── 4 Gráficas comparativas ───────────────────────────────────────────────
    st.markdown("### Comparación Bullpen Completo vs Disponible")
    st.caption("🔵 Completo | 🟠 Solo disponibles")

    df_g = df_liga[(df_liga["Team"] != "EQ31") & (df_liga["IP"] > 0)].sort_values("FIP").copy()
    x_rng = [-0.5, len(df_g) - 0.5]
    LAYOUT = dict(barmode="group", height=420, xaxis_tickangle=-45,
                  plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                  margin=dict(t=30, b=130), legend=dict(orientation="h", y=1.08))

    def _duo(df_s, col_c, col_d, ytitle, refs=None):
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Completo",    x=df_s["Nombre"], y=df_s[col_c],
                             marker_color="#1f77b4", opacity=0.85))
        if col_d in df_s.columns:
            fig.add_trace(go.Bar(name="Disponibles", x=df_s["Nombre"], y=df_s[col_d],
                                 marker_color="#ff7f0e", opacity=0.85))
        shapes = []
        if refs:
            for val, color in refs:
                shapes.append(dict(type="line", x0=x_rng[0], x1=x_rng[1],
                                   y0=val, y1=val, line=dict(color=color, dash="dash", width=1.5)))
        fig.update_layout(**{**LAYOUT, "yaxis_title": ytitle, "shapes": shapes})
        return fig

    st.markdown("#### FIP")
    st.plotly_chart(_duo(df_g, "FIP", "FIP_disp", "FIP",
                         [(3.50, "#28a745"), (4.20, "#dc3545")]), use_container_width=True)

    st.markdown("#### wOBA")
    df_wo = df_liga[df_liga["Team"] != "EQ31"].sort_values("wOBA").copy()
    st.plotly_chart(_duo(df_wo, "wOBA", "wOBA_disp", "wOBA",
                         [(0.310, "#28a745"), (0.340, "#dc3545")]), use_container_width=True)

    st.markdown("#### K%")
    df_kk = df_liga[df_liga["Team"] != "EQ31"].sort_values("K%", ascending=False).copy()
    st.plotly_chart(_duo(df_kk, "K%", "K%_disp", "K%",
                         [(25.0, "#28a745"), (20.0, "#dc3545")]), use_container_width=True)

    st.markdown("#### BB%")
    df_bb2 = df_liga[df_liga["Team"] != "EQ31"].sort_values("BB%").copy()
    st.plotly_chart(_duo(df_bb2, "BB%", "BB%_disp", "BB%",
                         [(8.0, "#28a745"), (10.5, "#dc3545")]), use_container_width=True)

    # ── Disponibilidad apilada ────────────────────────────────────────────────
    st.markdown(f"#### Disponibilidad — {fecha.strftime('%d %b %Y')}")
    df_dp = df_liga[df_liga["Team"] != "EQ31"].sort_values("Disp%", ascending=False)
    fig_disp = go.Figure()
    fig_disp.add_trace(go.Bar(name="Disponibles",    x=df_dp["Nombre"], y=df_dp["Disp"],    marker_color="#28a745"))
    fig_disp.add_trace(go.Bar(name="Limitados",      x=df_dp["Nombre"], y=df_dp["Limit"],   marker_color="#ffc107"))
    fig_disp.add_trace(go.Bar(name="No disponibles", x=df_dp["Nombre"], y=df_dp["NDisp"],   marker_color="#dc3545"))
    fig_disp.update_layout(barmode="stack", height=400, xaxis_tickangle=-45,
                           yaxis_title="# Relevistas", plot_bgcolor="rgba(0,0,0,0)",
                           paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=10, b=130),
                           legend=dict(orientation="h", y=1.05))
    st.plotly_chart(fig_disp, use_container_width=True)


# =============================================================================
# =============================================================================
# PARTIDOS DEL DÍA
# =============================================================================

_MLB_API_TO_INTERNAL = {"ATH": "OAK", "AZ": "ARI"}


# ── FB velo POR SALIDA (Statcast pitch-level) ────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def cargar_fb_velo_gamelog(pitcher_id: int, start_dt: str, end_dt: str) -> dict:
    """
    Retorna {fecha_str: avg_velo_fb} usando Statcast pitch-level.
    Filtra pitches tipo FF/SI/FT/FC del pitcher y agrupa por game_date.
    """
    if not HAS_PYBASEBALL:
        return {}
    _FB = {"FF", "FT", "SI", "FC", "FO"}
    try:
        from pybaseball import statcast_pitcher
        df = statcast_pitcher(start_dt, end_dt, pitcher_id)
        if df is None or df.empty:
            return {}
        df = df[df["pitch_type"].isin(_FB) & df["release_speed"].notna()]
        if df.empty:
            return {}
        df["game_date"] = pd.to_datetime(df["game_date"]).dt.strftime("%Y-%m-%d")
        result = {}
        for gd, grp in df.groupby("game_date"):
            result[str(gd)] = round(float(grp["release_speed"].mean()), 1)
        return result
    except Exception:
        return {}


# ── Récord del equipo (temporada + últimos 10 + local/visita + día semana) ────

@st.cache_data(ttl=1800, show_spinner=False)
def cargar_records_equipo(team_id: int, season: int = None) -> dict:
    """
    Retorna dict con:
      'season':   'W-L'
      'last10':   'W-L'
      'home10':   'W-L'
      'away10':   'W-L'
      'weekday':  {0: 'W-L', ..., 6: 'W-L'}   (0=Mon … 6=Sun)
    Fuente: MLB Stats API schedule con hydrate=decisions.
    """
    if season is None:
        season = 2026
    today = date.today()
    empty = {"season": "—", "last10": "—", "home10": "—", "away10": "—", "weekday": {}}

    # Solo usar la temporada indicada (2026), sin fallback a año anterior
    yr = season
    for _attempt in range(1):
        try:
            url = (
                "https://statsapi.mlb.com/api/v1/schedule"
                f"?sportId=1&teamId={team_id}&season={yr}&gameType=R"
                f"&startDate={yr}-01-01&endDate={today}"
                "&hydrate=decisions,team,linescore"
            )
            r = _req_http.get(url, timeout=15)
            r.raise_for_status()
            games = []
            for db in r.json().get("dates", []):
                for g in db.get("games", []):
                    status = g.get("status", {}).get("abstractGameState", "")
                    if status != "Final":
                        continue
                    gdate = g.get("gameDate", "")
                    try:
                        gdt   = datetime.fromisoformat(gdate.replace("Z", "+00:00"))
                        wday  = gdt.weekday()         # 0=Mon … 6=Sun
                    except Exception:
                        continue
                    h_id  = g["teams"]["home"]["team"].get("id")
                    a_id  = g["teams"]["away"]["team"].get("id")
                    h_score = g["teams"]["home"].get("score", 0) or 0
                    a_score = g["teams"]["away"].get("score", 0) or 0
                    is_home = (h_id == team_id)
                    if is_home:
                        won = h_score > a_score
                    else:
                        won = a_score > h_score
                    games.append({
                        "date": gdt, "home": is_home, "won": won, "wday": wday
                    })

            if not games:
                return empty

            # Ordenar por fecha
            games.sort(key=lambda x: x["date"])
            total_w = sum(1 for g in games if g["won"])
            total_l = len(games) - total_w
            season_rec = f"{total_w}-{total_l}"

            last10  = games[-10:]
            l10_w   = sum(1 for g in last10 if g["won"])
            last10_rec = f"{l10_w}-{len(last10)-l10_w}"

            home_g  = [g for g in games if g["home"]]
            h10     = home_g[-10:]
            h10_w   = sum(1 for g in h10 if g["won"])
            home10_rec = f"{h10_w}-{len(h10)-h10_w}" if h10 else "—"

            away_g  = [g for g in games if not g["home"]]
            a10     = away_g[-10:]
            a10_w   = sum(1 for g in a10 if g["won"])
            away10_rec = f"{a10_w}-{len(a10)-a10_w}" if a10 else "—"

            # Por día de la semana
            wd_rec = {}
            for wd in range(7):
                wdg = [g for g in games if g["wday"] == wd]
                if wdg:
                    ww = sum(1 for g in wdg if g["won"])
                    wd_rec[wd] = f"{ww}-{len(wdg)-ww}"

            return {
                "season": season_rec, "last10": last10_rec,
                "home10": home10_rec, "away10": away10_rec,
                "weekday": wd_rec,
            }
        except Exception:
            pass

    return empty


# ── Récord head-to-head entre dos equipos ─────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def cargar_h2h(team_id_home: int, team_id_away: int, season: int = None) -> str:
    """
    Retorna 'W-L' del equipo HOME vs equipo AWAY en la temporada.
    """
    if season is None:
        season = 2026
    today = date.today()
    yr = season
    try:
        url = (
            "https://statsapi.mlb.com/api/v1/schedule"
            f"?sportId=1&teamId={team_id_home}&season={yr}&gameType=R"
            f"&startDate={yr}-01-01&endDate={today}"
            "&hydrate=decisions,team,linescore"
        )
        r = _req_http.get(url, timeout=15)
        r.raise_for_status()
        wins = losses = 0
        for db in r.json().get("dates", []):
            for g in db.get("games", []):
                if g.get("status", {}).get("abstractGameState") != "Final":
                    continue
                h_id = g["teams"]["home"]["team"].get("id")
                a_id = g["teams"]["away"]["team"].get("id")
                if not ({h_id, a_id} == {team_id_home, team_id_away}):
                    continue
                h_s = g["teams"]["home"].get("score", 0) or 0
                a_s = g["teams"]["away"].get("score", 0) or 0
                if h_id == team_id_home:
                    if h_s > a_s: wins += 1
                    else: losses += 1
                else:
                    if a_s > h_s: wins += 1
                    else: losses += 1
        if wins + losses > 0:
            return f"{wins}-{losses}"
    except Exception:
        pass
    return "—"


# ── Standings de la liga (clasificación actual) ───────────────────────────────

@st.cache_data(ttl=14400, show_spinner=False)
def cargar_standings_liga(season: int = None) -> dict:
    """Retorna {team_id: {'wins': int, 'losses': int, 'pct': float}} para todos los equipos."""
    if season is None:
        season = date.today().year
    try:
        url = (
            "https://statsapi.mlb.com/api/v1/standings"
            f"?leagueId=103,104&season={season}&standingsTypes=regularSeason"
        )
        r = _req_http.get(url, timeout=12)
        r.raise_for_status()
        result = {}
        for rec in r.json().get("records", []):
            for tr in rec.get("teamRecords", []):
                tid = tr["team"].get("id")
                w = int(tr.get("wins", 0))
                l = int(tr.get("losses", 0))
                pct = round(w / (w + l), 3) if (w + l) > 0 else 0.0
                if tid:
                    result[tid] = {"wins": w, "losses": l, "pct": pct}
        return result
    except Exception:
        return {}


# ── SOS (Strength of Schedule) ────────────────────────────────────────────────

@st.cache_data(ttl=14400, show_spinner=False)
def cargar_sos_equipo(team_id: int, season: int = None) -> dict:
    """
    Retorna:
      sos_30d:    float | None  — win% promedio de oponentes en los últimos 30 días.
      sos_7d:     float | None  — win% promedio de oponentes en los próximos 7 días.
      sos_14d:    float | None  — win% promedio de oponentes en los próximos 14 días.
      rec_vs_500: str           — W-L del equipo vs rivales con win% ≥ 0.500 (últimos 46d).
      g_30d:      int           — partidos jugados en los últimos 30d.
      g_7d:       int           — partidos programados en los próximos 7d.
      g_14d:      int           — partidos programados en los próximos 14d.
    """
    if season is None:
        season = date.today().year
    today        = date.today()
    start_past   = today - timedelta(days=46)   # cubre SOS-30d Y récord vs .500 (46d)
    end_future   = today + timedelta(days=14)
    cutoff_30d   = today - timedelta(days=30)
    cutoff_7d_f  = today + timedelta(days=7)
    _empty = {
        "sos_30d": None, "sos_7d": None, "sos_14d": None,
        "rec_vs_500": "—", "g_30d": 0, "g_7d": 0, "g_14d": 0,
    }
    if not team_id:
        return _empty
    try:
        url = (
            "https://statsapi.mlb.com/api/v1/schedule"
            f"?sportId=1&teamId={team_id}&season={season}&gameType=R"
            f"&startDate={start_past.strftime('%Y-%m-%d')}&endDate={end_future.strftime('%Y-%m-%d')}"
            "&hydrate=team,linescore"
        )
        r = _req_http.get(url, timeout=15)
        r.raise_for_status()
        standings = cargar_standings_liga(season)

        past_games  = []   # {'opp_id': int, 'won': bool, 'gdate': date}
        future_opps = []   # {'opp_id': int, 'gdate': date}

        for db in r.json().get("dates", []):
            try:
                gdate = date.fromisoformat(db.get("date", ""))
            except Exception:
                continue
            for g in db.get("games", []):
                status  = g.get("status", {}).get("abstractGameState", "")
                h_id    = g["teams"]["home"]["team"].get("id")
                a_id    = g["teams"]["away"]["team"].get("id")
                is_home = (h_id == team_id)
                opp_id  = a_id if is_home else h_id

                if status == "Final" and gdate >= start_past:
                    h_s = g["teams"]["home"].get("score", 0) or 0
                    a_s = g["teams"]["away"].get("score", 0) or 0
                    won = (h_s > a_s) if is_home else (a_s > h_s)
                    past_games.append({"opp_id": opp_id, "won": won, "gdate": gdate})
                elif status not in ("Final", "In Progress") and gdate > today:
                    future_opps.append({"opp_id": opp_id, "gdate": gdate})

        # SOS últimos 30 días
        pcts_30 = [standings.get(g["opp_id"], {}).get("pct")
                   for g in past_games if g["gdate"] >= cutoff_30d
                   and standings.get(g["opp_id"], {}).get("pct") is not None]

        # Récord vs .500 — últimos 46 días (todos los past_games)
        w500 = l500 = 0
        for g in past_games:
            p = standings.get(g["opp_id"], {}).get("pct")
            if p is not None and p >= 0.500:
                if g["won"]: w500 += 1
                else:        l500 += 1

        # SOS próximos 7 días
        pcts_7 = [standings.get(g["opp_id"], {}).get("pct")
                  for g in future_opps if g["gdate"] <= cutoff_7d_f
                  and standings.get(g["opp_id"], {}).get("pct") is not None]

        # SOS próximos 14 días
        pcts_14 = [standings.get(g["opp_id"], {}).get("pct")
                   for g in future_opps
                   if standings.get(g["opp_id"], {}).get("pct") is not None]

        g_30d = sum(1 for g in past_games if g["gdate"] >= cutoff_30d)
        g_7d  = sum(1 for g in future_opps if g["gdate"] <= cutoff_7d_f)

        return {
            "sos_30d":    round(sum(pcts_30) / len(pcts_30), 3) if pcts_30 else None,
            "sos_7d":     round(sum(pcts_7)  / len(pcts_7),  3) if pcts_7  else None,
            "sos_14d":    round(sum(pcts_14) / len(pcts_14), 3) if pcts_14 else None,
            "rec_vs_500": f"{w500}-{l500}" if (w500 + l500) > 0 else "—",
            "g_30d":      g_30d,
            "g_7d":       g_7d,
            "g_14d":      len(future_opps),
        }
    except Exception:
        return _empty


# ── Récord vs mano del pitcher ────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def cargar_record_vs_hand(team_id: int, pitcher_hand: str, season: int = None) -> str:
    """
    Retorna 'W-L' del equipo enfrentando starters de la mano indicada en la temporada.
    Obtiene el schedule y filtra por mano del probable pitcher (o starter registrado).
    """
    if season is None:
        season = 2026
    today = date.today()
    yr = season
    try:
        url = (
            "https://statsapi.mlb.com/api/v1/schedule"
            f"?sportId=1&teamId={team_id}&season={yr}&gameType=R"
            f"&startDate={yr}-01-01&endDate={today}"
            "&hydrate=decisions,team,linescore,probablePitcher"
        )
        r = _req_http.get(url, timeout=15)
        r.raise_for_status()
        wins = losses = 0
        for db in r.json().get("dates", []):
            for g in db.get("games", []):
                if g.get("status", {}).get("abstractGameState") != "Final":
                    continue
                h_id  = g["teams"]["home"]["team"].get("id")
                a_id  = g["teams"]["away"]["team"].get("id")
                h_s   = g["teams"]["home"].get("score", 0) or 0
                a_s   = g["teams"]["away"].get("score", 0) or 0
                is_home = (h_id == team_id)
                # Pitcher RIVAL al equipo
                opp_side = g["teams"]["home"] if not is_home else g["teams"]["away"]
                pp_id    = (opp_side.get("probablePitcher") or {}).get("id")
                if not pp_id:
                    continue
                hand = _fetch_pitcher_hand(pp_id)
                if hand != pitcher_hand:
                    continue
                if is_home:
                    if h_s > a_s: wins += 1
                    else: losses += 1
                else:
                    if a_s > h_s: wins += 1
                    else: losses += 1
        if wins + losses > 0:
            return f"{wins}-{losses}"
    except Exception:
        pass
    return "—"


@st.cache_data(ttl=1800, show_spinner=False)
def cargar_record_equipo_con_pitcher(pitcher_id: int, team_id: int, season: int = None) -> str:
    """
    Retorna 'W-L' del equipo en partidos de temporada regular donde pitcher_id fue el abridor.
    Usa el gamelog del pitcher (MLB Stats API) cruzado con el schedule del equipo.
    """
    if not pitcher_id or not team_id:
        return "—"
    if season is None:
        season = 2026
    today = date.today()
    try:
        # 1. Gamelog del pitcher → set de gamePks donde fue abridor
        gl_url = (
            f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}/stats"
            f"?stats=gameLog&group=pitching&season={season}&gameType=R"
        )
        r1 = _req_http.get(gl_url, timeout=12)
        r1.raise_for_status()
        started_pks = set()
        for block in r1.json().get("stats", []):
            for split in block.get("splits", []):
                if int((split.get("stat") or {}).get("gamesStarted", 0)) >= 1:
                    gpk = (split.get("game") or {}).get("gamePk")
                    if gpk:
                        started_pks.add(int(gpk))

        if not started_pks:
            return "—"

        # 2. Schedule del equipo con scores → cruzar por gamePk
        sched_url = (
            "https://statsapi.mlb.com/api/v1/schedule"
            f"?sportId=1&teamId={team_id}&season={season}&gameType=R"
            f"&startDate={season}-01-01&endDate={today}"
            "&hydrate=team,linescore"
        )
        r2 = _req_http.get(sched_url, timeout=15)
        r2.raise_for_status()
        wins = losses = 0
        for db in r2.json().get("dates", []):
            for g in db.get("games", []):
                if int(g.get("gamePk", 0)) not in started_pks:
                    continue
                if g.get("status", {}).get("abstractGameState") != "Final":
                    continue
                h_id    = g["teams"]["home"]["team"].get("id")
                h_score = g["teams"]["home"].get("score", 0) or 0
                a_score = g["teams"]["away"].get("score", 0) or 0
                is_home = (h_id == team_id)
                if is_home:
                    if h_score > a_score: wins += 1
                    else: losses += 1
                else:
                    if a_score > h_score: wins += 1
                    else: losses += 1

        return f"{wins}-{losses}" if (wins + losses) > 0 else "—"
    except Exception:
        return "—"


# ── Clima del partido (Open-Meteo, sin API key) ───────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def cargar_clima_partido(team_abbr: str, game_dt_utc: str) -> dict | None:
    """
    Retorna dict con temp_c, temp_f, humidity, precip_prob, wind_kph,
    wind_deg, wind_rel_label, wind_emoji.
    game_dt_utc: ISO string en UTC (e.g. '2026-03-27T18:10:00Z').
    Retorna None si el estadio es techado o si falla la API.
    """
    if team_abbr in DOMED_STADIUMS:
        return None
    coords = VENUE_COORDS.get(team_abbr)
    if not coords:
        return None
    lat, lon = coords

    try:
        # Parsear datetime UTC
        from datetime import timezone as _tz
        gdt_utc = datetime.fromisoformat(game_dt_utc.replace("Z", "+00:00"))
        # Offset de timezone del estadio (approximado por longitud)
        tz_offset = round(lon / 15)
        local_tz  = _tz(timedelta(hours=tz_offset))
        gdt_local = gdt_utc.astimezone(local_tz)
        target_hour = gdt_local.replace(minute=0, second=0, microsecond=0)
        date_str    = target_hour.strftime("%Y-%m-%d")

        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&hourly=temperature_2m,relativehumidity_2m,precipitation_probability,"
            f"windspeed_10m,winddirection_10m"
            f"&start_date={date_str}&end_date={date_str}"
            f"&timezone=auto"
        )
        r = _req_http.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        times    = data["hourly"]["time"]
        temps    = data["hourly"]["temperature_2m"]
        humid    = data["hourly"]["relativehumidity_2m"]
        precip   = data["hourly"]["precipitation_probability"]
        wspeed   = data["hourly"]["windspeed_10m"]
        wdir     = data["hourly"]["winddirection_10m"]

        # Buscar la hora más cercana al juego
        target_str = target_hour.strftime("%Y-%m-%dT%H:%M")
        best_idx   = 0
        for idx, t in enumerate(times):
            if t[:16] == target_str:
                best_idx = idx
                break

        temp_c   = temps[best_idx]
        temp_f   = round(temp_c * 9 / 5 + 32, 1)
        hum      = humid[best_idx]
        p_rain   = precip[best_idx]
        w_kph    = wspeed[best_idx]
        w_deg    = wdir[best_idx]

        # Dirección del viento relativa al campo
        cf_bear  = STADIUM_CF_BEARING.get(team_abbr, 0)
        # Ángulo del viento relativo al eje HP→CF
        rel_deg  = (w_deg - cf_bear) % 360
        # rel_deg: 0 = viento que sale (sopla de HP hacia CF)
        #          180 = viento que entra (sopla de CF hacia HP)
        if w_kph < 5:
            wind_lbl   = "Sin viento"
            wind_emoji = "🌬️"
        elif rel_deg <= 45 or rel_deg >= 315:
            wind_lbl   = "Saliendo (a CF)"
            wind_emoji = "⬆️"
        elif 135 <= rel_deg <= 225:
            wind_lbl   = "Entrando (a HP)"
            wind_emoji = "⬇️"
        else:
            wind_lbl   = "Lateral"
            wind_emoji = "↔️"

        # Emoji de lluvia
        if p_rain >= 60:
            rain_emoji = "🌧️"
        elif p_rain >= 30:
            rain_emoji = "🌦️"
        else:
            rain_emoji = "☀️"

        return {
            "temp_c":     temp_c,
            "temp_f":     temp_f,
            "humidity":   hum,
            "precip_prob": p_rain,
            "wind_kph":   w_kph,
            "wind_deg":   w_deg,
            "wind_rel":   wind_lbl,
            "wind_emoji": wind_emoji,
            "rain_emoji": rain_emoji,
        }
    except Exception:
        return None


# ── Momios FanDuel via The Odds API ──────────────────────────────────────────

def cargar_momios_fanduel(api_key: str) -> dict:
    """
    Retorna {home_name_lower: {'home_ml': int, 'away_ml': int, 'home_team': str, 'away_team': str}}
    Usa The Odds API (the-odds-api.com). Fallback silencioso si falla.
    """
    if not api_key or len(api_key) < 10:
        return {}
    try:
        url = (
            "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/"
            f"?apiKey={api_key}&regions=us&markets=h2h&bookmakers=fanduel&oddsFormat=american"
        )
        r = _req_http.get(url, timeout=10)
        if r.status_code != 200:
            return {}
        result = {}
        for game in r.json():
            home = game.get("home_team", "")
            away = game.get("away_team", "")
            for bk in game.get("bookmakers", []):
                if bk.get("key") != "fanduel":
                    continue
                for mkt in bk.get("markets", []):
                    if mkt.get("key") != "h2h":
                        continue
                    odds = {o["name"]: o["price"] for o in mkt.get("outcomes", [])}
                    home_ml = odds.get(home)
                    away_ml = odds.get(away)
                    if home_ml is not None and away_ml is not None:
                        key = home.lower().strip()
                        result[key] = {
                            "home_team": home, "away_team": away,
                            "home_ml": int(home_ml), "away_ml": int(away_ml),
                        }
        return result
    except Exception:
        return {}


def _ml_to_prob(ml: int) -> float:
    """Convierte moneyline americano a probabilidad implícita (sin vig)."""
    if ml > 0:
        return 100 / (ml + 100)
    else:
        return abs(ml) / (abs(ml) + 100)


def _prob_to_ml(p: float) -> str:
    """Convierte probabilidad a moneyline americano formateado."""
    if p <= 0 or p >= 1:
        return "—"
    if p >= 0.5:
        ml = round(-(p / (1 - p)) * 100)
        return f"{ml}"
    else:
        ml = round((1 - p) / p * 100)
        return f"+{ml}"


def _fmt_ml(ml: int) -> str:
    return f"+{ml}" if ml > 0 else str(ml)


def _match_momio(momios: dict, home_name: str, away_name: str) -> dict:
    """
    Busca el momio que corresponde al partido por nombre de equipo.
    Retorna {} si no encuentra.
    """
    if not momios:
        return {}
    h_low = home_name.lower().strip()
    a_low = away_name.lower().strip()
    for key, val in momios.items():
        vh = val["home_team"].lower().strip()
        va = val["away_team"].lower().strip()
        if (h_low in vh or vh in h_low) and (a_low in va or va in a_low):
            return val
        if (a_low in vh or vh in a_low) and (h_low in va or va in h_low):
            # invertido en la API
            return {
                "home_team": val["away_team"], "away_team": val["home_team"],
                "home_ml": val["away_ml"], "away_ml": val["home_ml"],
            }
    return {}


# ── Lineup confirmado (MLB Stats API) ────────────────────────────────────────

def _lineup_cache_bucket() -> str:
    """Bucket que cambia cada 10 min entre 10am-7pm CDMX, cada 60 min el resto."""
    now = datetime.utcnow() - timedelta(hours=6)
    if 10 <= now.hour < 19:
        return now.strftime("%Y%m%d%H") + str(now.minute // 10)
    return now.strftime("%Y%m%d%H")


@st.cache_data(ttl=3600, show_spinner=False)
def cargar_lineup_partido(game_pk: int, cache_bucket: str = "") -> dict:
    """
    Retorna {'home': [...], 'away': [...]} con el lineup confirmado.
    Cada elemento: {'nombre': str, 'pos': str, 'order': int, 'wOBA': float|None, 'wRC+': int|None}
    cache_bucket controla la frecuencia de refresco (10 min peak / 60 min off-peak).
    wOBA y wRC+ calculados desde seasonStats.batting del boxscore.
    """
    empty = {"home": [], "away": []}
    if not game_pk:
        return empty

    def _calc_woba(s: dict):
        try:
            ab  = int(s.get("atBats", 0) or 0)
            bb  = int(s.get("baseOnBalls", 0) or 0)
            hbp = int(s.get("hitByPitch", 0) or 0)
            h   = int(s.get("hits", 0) or 0)
            d2  = int(s.get("doubles", 0) or 0)
            d3  = int(s.get("triples", 0) or 0)
            hr  = int(s.get("homeRuns", 0) or 0)
            sf  = int(s.get("sacFlies", 0) or 0)
            singles = max(0, h - d2 - d3 - hr)
            denom   = ab + bb + hbp + sf
            if denom == 0:
                return None, None
            woba = round((0.69*bb + 0.72*hbp + 0.89*singles + 1.27*d2 + 1.62*d3 + 2.10*hr) / denom, 3)
            wrc_plus = round((woba / 0.320) * 100)
            return woba, wrc_plus
        except Exception:
            return None, None

    try:
        url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
        r = _req_http.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        teams = data.get("teams", {})
        result = {}
        for side in ("home", "away"):
            players = teams.get(side, {}).get("players", {})
            order_map = teams.get(side, {}).get("battingOrder", [])
            lineup = []
            for i, pid_str in enumerate(order_map):
                pid_key = f"ID{pid_str}"
                p = players.get(pid_key, {})
                info = p.get("person", {})
                pos  = p.get("position", {}).get("abbreviation", "—")
                s_bat = (p.get("seasonStats") or {}).get("batting", {})
                woba, wrc = _calc_woba(s_bat)
                lineup.append({
                    "order":  i + 1,
                    "nombre": info.get("fullName", "—"),
                    "pos":    pos,
                    "wOBA":   woba,
                    "wRC+":   wrc,
                })
            result[side] = lineup
        return result if result else empty
    except Exception:
        return empty


import json
import os


# ── Fastball velocity (MLB Stats API pitch arsenal) ───────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def cargar_fb_velo(pitcher_id: int) -> float | None:
    """Avg fastball velo (FF/SI/FT/FC) desde MLB Stats API pitch arsenal."""
    _FB_TYPES = {"FF", "FT", "SI", "FC", "FO"}
    season = date.today().year
    for yr in (season, season - 1):
        try:
            url = (
                f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}/stats"
                f"?stats=pitchArsenal&group=pitching&season={yr}&gameType=R"
            )
            r = _req_http.get(url, timeout=10)
            r.raise_for_status()
            best_velo, best_cnt = None, 0
            for block in r.json().get("stats", []):
                for split in block.get("splits", []):
                    s  = split.get("stat", {})
                    pt = (s.get("type", {}) or {}).get("code", "")
                    if pt not in _FB_TYPES:
                        continue
                    velo = s.get("averageSpeed") or s.get("avgSpeed")
                    cnt  = int(s.get("totalPitches", s.get("count", 0)) or 0)
                    if velo and cnt > best_cnt:
                        best_velo, best_cnt = round(float(velo), 1), cnt
            if best_velo:
                return best_velo
        except Exception:
            pass
    return None


# ── Pitcher handedness ────────────────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_pitcher_hand(pitcher_id: int) -> str:
    """Retorna 'R' o 'L'. Default 'R'."""
    try:
        url = f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}"
        r = _req_http.get(url, timeout=8)
        r.raise_for_status()
        people = r.json().get("people", [{}])
        if people:
            return people[0].get("pitchHand", {}).get("code", "R")
    except Exception:
        pass
    return "R"


# ── Batting stats from Statcast ───────────────────────────────────────────────

def _batting_from_statcast(
    raw: pd.DataFrame,
    p_throws: str = None,
    min_inning: int = None,
    min_pa: int = 20,
) -> dict:
    """
    Retorna {team_abbr: {'wOBA': float, 'wRC+': int, 'PA': int}}.
    team_abbr en formato interno (ARI, OAK...).
    p_throws: 'R' o 'L' para filtrar por mano del pitcher.
    min_inning: filtra inning >= min_inning.
    """
    if raw.empty or "woba_value" not in raw.columns:
        return {}
    df = raw.copy()
    if p_throws and "p_throws" in df.columns:
        df = df[df["p_throws"] == p_throws]
    if min_inning is not None and "inning" in df.columns:
        df = df[df["inning"] >= min_inning]
    if df.empty:
        return {}
    if "inning_topbot" not in df.columns or "home_team" not in df.columns:
        return {}

    df = df.copy()
    df["batting_team_sc"] = np.where(
        df["inning_topbot"] == "Top", df["away_team"], df["home_team"]
    )
    df["batting_team"] = df["batting_team_sc"].map(lambda x: SC_TO_INT.get(x, x))

    df_pa = df[df["events"].notna() & df["events"].isin(PA_EVENTS)].copy()
    if df_pa.empty:
        return {}

    total_w  = df_pa["woba_value"].fillna(0).sum()
    total_pa = len(df_pa)
    lg_woba  = total_w / total_pa if total_pa > 0 else 0.320

    result = {}
    for team, grp in df_pa.groupby("batting_team"):
        pa = len(grp)
        if pa < min_pa:
            continue
        woba    = round(grp["woba_value"].fillna(0).sum() / pa, 3)
        wrc_plus = round((woba / lg_woba) * 100) if lg_woba > 0 else 100
        result[str(team)] = {"wOBA": woba, "wRC+": wrc_plus, "PA": pa}
    return result


# ── Bateo con RISP ────────────────────────────────────────────────────────────

def _batting_risp_from_statcast(raw: pd.DataFrame, min_pa: int = 10) -> dict:
    """
    Retorna {team_abbr: {'wOBA': float, 'AVG': float, 'PA': int}} con bateo
    en situaciones RISP (corredor en 2B y/o 3B), sin filtro de mano del pitcher.
    Liga completa para ranking entre los 30 equipos.
    """
    if raw.empty or "woba_value" not in raw.columns:
        return {}
    risp_cols = [c for c in ["on_2b", "on_3b"] if c in raw.columns]
    if not risp_cols:
        return {}
    df = raw.copy()
    # RISP = al menos un corredor en 2B o 3B
    risp_mask = pd.Series(False, index=df.index)
    for col in risp_cols:
        risp_mask |= df[col].notna()
    df = df[risp_mask]
    if df.empty:
        return {}
    if "inning_topbot" not in df.columns or "home_team" not in df.columns:
        return {}
    df["batting_team_sc"] = np.where(
        df["inning_topbot"] == "Top", df["away_team"], df["home_team"]
    )
    df["batting_team"] = df["batting_team_sc"].map(lambda x: SC_TO_INT.get(x, x))
    df_pa = df[df["events"].notna() & df["events"].isin(PA_EVENTS)].copy()
    if df_pa.empty:
        return {}
    # Para AVG: hits = single, double, triple, HR
    hit_events = {"single", "double", "triple", "home_run"}
    total_w  = df_pa["woba_value"].fillna(0).sum()
    total_pa = len(df_pa)
    lg_woba  = total_w / total_pa if total_pa > 0 else 0.320
    result = {}
    for team, grp in df_pa.groupby("batting_team"):
        pa = len(grp)
        if pa < min_pa:
            continue
        woba = round(grp["woba_value"].fillna(0).sum() / pa, 3)
        hits = int(grp["events"].isin(hit_events).sum())
        ab   = int(grp["events"].isin(
            hit_events | {"strikeout", "field_out", "force_out",
                          "grounded_into_double_play", "double_play",
                          "fielders_choice_out", "fielders_choice"}
        ).sum())
        avg  = round(hits / ab, 3) if ab > 0 else 0.0
        wrc_plus = round((woba / lg_woba) * 100) if lg_woba > 0 else 100
        result[str(team)] = {"wOBA": woba, "AVG": avg, "wRC+": wrc_plus, "PA": pa}
    return result


# ── Hot hitters (MLB Stats API) ───────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def cargar_hot_hitters(team_id: int, dias: int = 14) -> list:
    """Top 5 bateadores por wOBA en los últimos `dias` días. Mín. 5 PA.
    La API byDateRange devuelve una fila acumulada por jugador para el rango."""
    if not team_id:
        return []
    today    = date.today()
    start_dt = today - timedelta(days=dias)

    def _fetch(s_date, e_date, season):
        try:
            url = (
                "https://statsapi.mlb.com/api/v1/stats"
                f"?stats=byDateRange&group=hitting"
                f"&startDate={s_date}&endDate={e_date}"
                f"&season={season}&sportId=1&gameType=R"
                f"&teamId={team_id}&limit=300"
            )
            r = _req_http.get(url, timeout=15)
            r.raise_for_status()
            data = r.json().get("stats", [])
            if not data:
                return []
            return data[0].get("splits", [])
        except Exception:
            return []

    def _splits_to_rows(splits):
        rows = []
        for sp in splits:
            s   = sp.get("stat", {})
            pa  = int(s.get("plateAppearances", 0))
            if pa < 5:
                continue
            ab      = int(s.get("atBats", 0))
            bb      = int(s.get("baseOnBalls", 0))
            hbp     = int(s.get("hitByPitch", 0))
            hits    = int(s.get("hits", 0))
            d2      = int(s.get("doubles", 0))
            d3      = int(s.get("triples", 0))
            hr      = int(s.get("homeRuns", 0))
            sf      = int(s.get("sacFlies", 0))
            singles = max(0, hits - d2 - d3 - hr)
            denom   = ab + bb + hbp + sf
            woba    = round(
                (0.69*bb + 0.72*hbp + 0.89*singles + 1.27*d2 + 1.62*d3 + 2.10*hr) / denom, 3
            ) if denom > 0 else 0.0
            ops = float(s.get("ops", 0) or 0)
            rows.append({
                "Bateador": sp.get("player", {}).get("fullName", "—"),
                "PA":   pa,
                "wOBA": woba,
                "OPS":  round(ops, 3),
                "HR":   hr,
            })
        return sorted(rows, key=lambda x: x["wOBA"], reverse=True)[:5]

    season = today.year
    splits = _fetch(start_dt.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"), season)
    return _splits_to_rows(splits)


# ── WAR líderes por equipo (FanGraphs via pybaseball) ────────────────────────

@st.cache_data(ttl=7200, show_spinner=False)
def cargar_war_equipo(team_abbr: str) -> list:
    """Top 3 jugadores por WAR acumulado en temporada (FanGraphs). Fallback año anterior."""
    if not HAS_PYBASEBALL:
        return []
    season = date.today().year
    for yr in (season, season - 1):
        try:
            from pybaseball import fg_batting_data
            df = fg_batting_data(yr, yr, qual=0)
            if df is None or df.empty:
                continue
            team_col = next((c for c in ["Team", "team"] if c in df.columns), None)
            name_col = next((c for c in ["Name", "PlayerName"] if c in df.columns), None)
            war_col  = next((c for c in ["WAR", "fWAR"] if c in df.columns), None)
            if not team_col or not name_col or not war_col:
                continue
            df_t = df[df[team_col] == team_abbr]
            if df_t.empty:
                continue
            df_t = df_t.sort_values(war_col, ascending=False).head(3)
            result = [
                {"Jugador": str(row[name_col]), "WAR": round(float(row[war_col]), 1)}
                for _, row in df_t.iterrows()
            ]
            if result:
                return result
        except Exception:
            pass
    return []


# ── Helpers game log iniciadores ──────────────────────────────────────────────

def _ip_decimal(ip_str) -> float:
    """'6.2' → 6.667 (notación béisbol)."""
    try:
        s = str(ip_str)
        if "." in s:
            inn, outs = s.split(".", 1)
            return int(inn) + int(outs) / 3
        return float(s)
    except Exception:
        return 0.0


def _fetch_gamelog_raw(pitcher_id: int, season: int) -> list:
    try:
        url = (
            f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}/stats"
            f"?stats=gameLog&group=pitching&season={season}&gameType=R"
        )
        r = _req_http.get(url, timeout=12)
        r.raise_for_status()
        for block in r.json().get("stats", []):
            splits = block.get("splits", [])
            if splits:
                return splits
        return []
    except Exception:
        return []


@st.cache_data(ttl=600, show_spinner=False)
def cargar_gamelog_pitcher(pitcher_id: int, n_starts: int = 4) -> pd.DataFrame:
    """Últimas n_starts salidas del pitcher (solo starts). Fallback año anterior si sin datos.
    Incluye columna 'FB mph' con velocidad promedio de fastball por salida (Statcast)."""
    current_year = date.today().year
    splits = _fetch_gamelog_raw(pitcher_id, current_year)
    if not splits:
        splits = _fetch_gamelog_raw(pitcher_id, current_year - 1)
    if not splits:
        return pd.DataFrame()

    rows = []
    for sp in splits:
        s = sp.get("stat", {})
        if int(s.get("gamesStarted", 0)) == 0:
            continue
        ip = _ip_decimal(s.get("inningsPitched", "0.0"))
        bf = int(s.get("battersFaced", 0))
        k  = int(s.get("strikeOuts", 0))
        bb = int(s.get("baseOnBalls", 0))
        hr = int(s.get("homeRuns", 0))
        er = int(s.get("earnedRuns", 0))
        era = round(er / ip * 9, 2) if ip > 0 else 0.0
        fip = round(max(0.0, (13*hr + 3*bb - 2*k) / ip + 3.10), 2) if ip > 0 else 0.0
        rows.append({
            "Fecha":   sp.get("date", ""),
            "Rival":   sp.get("opponent", {}).get("name", "—"),
            "IP":      round(ip, 1),
            "BF":      bf,
            "K":       k,  "BB":   bb,
            "HR":      hr, "ER":   er,
            "K%":      round(k / bf * 100, 2) if bf > 0 else 0.0,
            "BB%":     round(bb / bf * 100, 2) if bf > 0 else 0.0,
            "ERA":     era,
            "FIP":     fip,
            "ERA-FIP": round(era - fip, 2),
        })

    if not rows:
        return pd.DataFrame()

    df = (pd.DataFrame(rows)
          .sort_values("Fecha", ascending=False)
          .reset_index(drop=True)
          .head(n_starts))

    # Enriquecer con FB velo por salida (Statcast)
    if not df.empty:
        min_date = df["Fecha"].min()
        max_date = df["Fecha"].max()
        velo_map = cargar_fb_velo_gamelog(pitcher_id, min_date, max_date)
        df["FB mph"] = df["Fecha"].map(lambda d: velo_map.get(str(d), None))

    return df


def _resumen_gamelog(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    ip = sum(_ip_decimal(x) for x in df["IP"])
    bf = df["BF"].sum(); k = df["K"].sum()
    bb = df["BB"].sum(); hr = df["HR"].sum()
    er = df["ER"].sum(); n = len(df)
    era = round(er / ip * 9, 2) if ip > 0 else 0.0
    fip = round(max(0.0, (13*hr + 3*bb - 2*k) / ip + 3.10), 2) if ip > 0 else 0.0
    # Fecha del último start (primera fila porque viene ordenado desc)
    try:
        last_date = date.fromisoformat(str(df["Fecha"].iloc[0]))
    except Exception:
        last_date = None
    return {
        "n":         n,
        "IP":        round(ip, 1),
        "K%":        round(k / bf * 100, 2) if bf > 0 else 0.0,
        "BB%":       round(bb / bf * 100, 2) if bf > 0 else 0.0,
        "ERA":       era,
        "FIP":       fip,
        "ERA-FIP":   round(era - fip, 2),
        "last_date": last_date,
    }


@st.cache_data(ttl=1800, show_spinner=False)
def cargar_ranking_starters_mes() -> pd.DataFrame:
    """
    Ranking de iniciadores últimos 30 días. Califica: >= 2 GS en 30d Y >= 2 GS en 14d.
    Ordenado por FIP.
    """
    today = date.today()
    s30   = today - timedelta(days=30)
    s14   = today - timedelta(days=14)

    def _fetch(start, end):
        try:
            url = (
                "https://statsapi.mlb.com/api/v1/stats"
                f"?stats=byDateRange&group=pitching"
                f"&startDate={start}&endDate={end}"
                f"&sportId=1&gameType=R&limit=2000"
            )
            r = _req_http.get(url, timeout=15)
            r.raise_for_status()
            return r.json().get("stats", [{}])[0].get("splits", [])
        except Exception:
            return []

    splits_30 = _fetch(s30, today)
    splits_14 = _fetch(s14, today)

    ids_14 = {
        sp.get("player", {}).get("id")
        for sp in splits_14
        if int(sp.get("stat", {}).get("gamesStarted", 0)) >= 2
    }

    rows = []
    for sp in splits_30:
        pid  = sp.get("player", {}).get("id")
        name = sp.get("player", {}).get("fullName", "—")
        team_api = sp.get("team", {}).get("abbreviation", "—")
        team = _MLB_API_TO_INTERNAL.get(team_api, team_api)
        s    = sp.get("stat", {})
        gs   = int(s.get("gamesStarted", 0))
        if gs < 2 or pid not in ids_14:
            continue
        ip = _ip_decimal(s.get("inningsPitched", "0"))
        bf = int(s.get("battersFaced", 0))
        k  = int(s.get("strikeOuts", 0))
        bb = int(s.get("baseOnBalls", 0))
        hr = int(s.get("homeRuns", 0))
        er = int(s.get("earnedRuns", 0))
        era = round(er / ip * 9, 2) if ip > 0 else 99.0
        fip = round(max(0.0, (13*hr + 3*bb - 2*k) / ip + 3.10), 2) if ip > 0 else 99.0
        rows.append({
            "pitcher_id": pid, "Pitcher": name, "Team": team,
            "GS": gs, "IP": round(ip, 1),
            "K%": round(k / bf * 100, 2) if bf > 0 else 0.0,
            "BB%": round(bb / bf * 100, 2) if bf > 0 else 0.0,
            "ERA": era, "FIP": fip, "ERA-FIP": round(era - fip, 2),
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).sort_values("FIP").reset_index(drop=True)
    df.insert(0, "Rank_mes", range(1, len(df) + 1))
    return df


# =============================================================================
# ARTÍCULO EXTERNO — Fetch & parse de análisis de pitchers
# =============================================================================

def _normalizar_nombre(nombre: str) -> str:
    """Quita tildes y pasa a minúsculas para comparaciones."""
    nfkd = unicodedata.normalize("NFKD", nombre)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_article_pitcher_info(url: str) -> dict:
    """
    Descarga el artículo del URL y extrae bloques de texto.
    Devuelve {"blocks": [...], "full_text": "...", "error": ""}.
    """
    if not url:
        return {"blocks": [], "full_text": "", "error": ""}
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        resp = _req_http.get(url, headers=headers, timeout=20)
        resp.raise_for_status()

        if HAS_BS4:
            soup = _BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            blocks = []
            for tag in soup.find_all(["p", "li", "h2", "h3", "h4"]):
                txt = tag.get_text(separator=" ", strip=True)
                if len(txt) > 15:
                    blocks.append(txt)
        else:
            # Fallback: regex simple sobre el HTML
            text = re.sub(r"<[^>]+>", " ", resp.text)
            text = re.sub(r"\s+", " ", text)
            blocks = [s.strip() for s in text.split(".") if len(s.strip()) > 30]

        full_text = "\n".join(blocks)
        return {"blocks": blocks, "full_text": full_text, "error": ""}
    except Exception as exc:
        return {"blocks": [], "full_text": "", "error": str(exc)}


def _buscar_pitcher_en_articulo(pitcher_name: str, article_data: dict) -> str:
    """
    Busca menciones del pitcher en los bloques del artículo.
    Usa apellido (y opcionalmente nombre) para matching.
    Devuelve el texto relevante o cadena vacía.
    """
    if not article_data or not pitcher_name or pitcher_name == "Por confirmar":
        return ""
    blocks = article_data.get("blocks", [])
    if not blocks:
        return ""

    partes = pitcher_name.strip().split()
    apellido = _normalizar_nombre(partes[-1]) if partes else ""
    nombre   = _normalizar_nombre(partes[0])  if len(partes) > 1 else ""

    relevantes = []
    for blk in blocks:
        blk_norm = _normalizar_nombre(blk)
        # Buscar por apellido completo como palabra
        if apellido and re.search(r"\b" + re.escape(apellido) + r"\b", blk_norm):
            relevantes.append(blk)

    # Si hay demasiados hits por apellido muy común, filtrar con nombre también
    if len(relevantes) > 6 and nombre:
        filtrados = [b for b in relevantes
                     if re.search(r"\b" + re.escape(nombre) + r"\b",
                                  _normalizar_nombre(b))]
        if filtrados:
            relevantes = filtrados

    if not relevantes:
        return ""

    return "\n\n".join(relevantes[:6])


@st.cache_data(ttl=1800, show_spinner=False)
def cargar_partidos_mlb(fecha: date) -> list:
    try:
        url = (
            "https://statsapi.mlb.com/api/v1/schedule"
            f"?sportId=1&date={fecha}&hydrate=probablePitcher,team,venue,gameInfo"
        )
        r = _req_http.get(url, timeout=12)
        r.raise_for_status()
        data = r.json()
        games = []
        for date_block in data.get("dates", []):
            for g in date_block.get("games", []):
                h = g["teams"]["home"]; a = g["teams"]["away"]
                h_api = h["team"].get("abbreviation", "")
                a_api = a["team"].get("abbreviation", "")
                h_int = _MLB_API_TO_INTERNAL.get(h_api, h_api)
                a_int = _MLB_API_TO_INTERNAL.get(a_api, a_api)
                try:
                    from datetime import timezone as _tz
                    gdt      = datetime.fromisoformat(g.get("gameDate", "").replace("Z", "+00:00"))
                    cdmx_tz  = _tz(timedelta(hours=-6))
                    cdmx_dt  = gdt.astimezone(cdmx_tz)
                    hora_str = cdmx_dt.strftime("%I:%M %p CDMX")
                except Exception:
                    hora_str = "—"
                games.append({
                    "home_abbr":       h_int, "away_abbr":       a_int,
                    "home_name":       h["team"].get("name", h_int),
                    "away_name":       a["team"].get("name", a_int),
                    "home_pitcher":    h.get("probablePitcher", {}).get("fullName", "Por confirmar"),
                    "away_pitcher":    a.get("probablePitcher", {}).get("fullName", "Por confirmar"),
                    "home_pitcher_id": h.get("probablePitcher", {}).get("id"),
                    "away_pitcher_id": a.get("probablePitcher", {}).get("id"),
                    "hora": hora_str,
                    "game_date_utc": g.get("gameDate", ""),
                    "venue": g.get("venue", {}).get("name", "—"),
                    "game_pk": g.get("gamePk"),
                })
        return games
    except Exception as e:
        st.warning(f"Error cargando partidos: {e}")
        return []


def _bull_disp(raw_global: pd.DataFrame, team: str, fecha: date) -> dict:
    df_t = _extraer_apariciones_equipo(raw_global, team)
    if df_t.empty:
        return {"FIP": None, "K%": None, "BB%": None, "wOBA": None, "n_disp": 0, "n_total": 0}
    df_t = _filtrar_calificados(df_t, min_juegos=1)
    if df_t.empty:
        return {"FIP": None, "K%": None, "BB%": None, "wOBA": None, "n_disp": 0, "n_total": 0}
    d1 = fecha - timedelta(days=1); d2 = fecha - timedelta(days=2)
    ids_disp = set()
    for pid, grp in df_t.groupby("pitcher_id"):
        dates = set(grp["game_date"])
        pit_d1 = d1 in dates; pit_d2 = d2 in dates
        p_d1 = int(grp[grp["game_date"]==d1]["pitches"].sum()) if pit_d1 else 0
        p_d2 = int(grp[grp["game_date"]==d2]["pitches"].sum()) if pit_d2 else 0
        if not ((pit_d1 and pit_d2) or (pit_d1 and p_d1 > 30)):
            ids_disp.add(pid)
    n_total = df_t["pitcher_id"].nunique(); n_disp = len(ids_disp)
    df_d = df_t[df_t["pitcher_id"].isin(ids_disp)]
    if df_d.empty or df_d["IP"].sum() == 0:
        return {"FIP": None, "K%": None, "BB%": None, "wOBA": None, "n_disp": n_disp, "n_total": n_total}
    s = _stats_agregadas(df_d)
    return {**s, "n_disp": n_disp, "n_total": n_total}


def tab_partidos_dia():  # noqa: C901
    st.markdown("## Partidos del Día — Iniciadores & Bullpen Disponible")

    # Default: hoy si antes de las 21:00 CDMX (UTC-6), mañana si después
    _now_cdmx = datetime.utcnow() - timedelta(hours=6)
    _default_fecha = date(_now_cdmx.year, _now_cdmx.month, _now_cdmx.day)
    if _now_cdmx.hour >= 21:
        _default_fecha += timedelta(days=1)

    col_fd, col_btn = st.columns([2, 1])
    with col_fd:
        fecha_sel = st.date_input("Fecha de los partidos",
                                  value=_default_fecha,
                                  key="partidos_fecha")
    with col_btn:
        st.markdown(" ")
        st.button("Actualizar", type="primary", key="partidos_btn")

    with st.spinner("Cargando schedule MLB..."):
        partidos = cargar_partidos_mlb(fecha_sel)

    if not partidos:
        st.warning(f"Sin partidos para el {fecha_sel.strftime('%d %b %Y')}.")
        return

    tbd = sum(1 for p in partidos if "confirmar" in p["home_pitcher"].lower()
              or "confirmar" in p["away_pitcher"].lower())
    c1, c2, c3 = st.columns(3)
    c1.metric("Partidos", len(partidos))
    c2.metric("Con starter confirmado", len(partidos) - tbd)
    c3.metric("Por confirmar", tbd)

    # ── Artículo externo de análisis de pitchers ──────────────────────────────
    with st.container(border=True):
        st.markdown("##### 📰 Artículo de análisis de pitchers (Pitcher List u otro)")
        _col_url, _col_btn_art = st.columns([5, 1])
        with _col_url:
            _article_url_input = st.text_input(
                "Link del artículo",
                value=st.session_state.get("partidos_article_url", ""),
                key="partidos_article_url_input",
                placeholder="https://pitcherlist.com/...",
                label_visibility="collapsed",
            )
        with _col_btn_art:
            _read_btn = st.button("📖 Leer", key="fetch_article_btn", use_container_width=True)
        if _read_btn:
            st.session_state["partidos_article_url"] = _article_url_input.strip()
            st.rerun()

    _active_article_url = st.session_state.get("partidos_article_url", "")
    _article_data: dict = {}
    if _active_article_url:
        with st.spinner("Leyendo artículo..."):
            _article_data = _fetch_article_pitcher_info(_active_article_url)
        if _article_data.get("error"):
            st.warning(f"⚠️ No se pudo leer el artículo: {_article_data['error']}")
        elif _article_data.get("full_text"):
            st.caption(f"✅ Artículo cargado — {len(_article_data.get('blocks', []))} bloques de texto extraídos")

    # ── Ranking mensual ───────────────────────────────────────────────────────
    with st.spinner("Cargando ranking mensual de iniciadores..."):
        df_rank_mes = cargar_ranking_starters_mes()
    rank_mes_lookup: dict = {}
    n_rank_mes = 0
    if not df_rank_mes.empty:
        n_rank_mes = len(df_rank_mes)
        for _, _row in df_rank_mes.iterrows():
            rank_mes_lookup[int(_row["pitcher_id"])] = int(_row["Rank_mes"])

    # ── IDs de todos los iniciadores ─────────────────────────────────────────
    all_pids: set = set()
    for p in partidos:
        for _k in ("home_pitcher_id", "away_pitcher_id"):
            if p.get(_k):
                all_pids.add(p[_k])

    # ── Game logs + mano + velo (en paralelo de cache) ────────────────────────
    gamelogs: dict = {}
    pitcher_hands: dict = {}
    pitcher_velos: dict = {}
    with st.spinner("Cargando stats & velo de iniciadores..."):
        for pid in all_pids:
            gamelogs[pid]      = cargar_gamelog_pitcher(pid, n_starts=4)
            pitcher_hands[pid] = _fetch_pitcher_hand(pid)
            pitcher_velos[pid] = cargar_fb_velo(pid)

    # Sin filtro de 60 días — incluir todas las salidas disponibles
    gamelogs_60: dict = {}
    resumenes: dict   = {}
    for pid, df in gamelogs.items():
        gamelogs_60[pid] = df if not df.empty else pd.DataFrame()
        resumenes[pid]   = _resumen_gamelog(df) if not df.empty else {}

    # ── Ranking diario (slate) ─────────────────────────────────────────────────
    slate_items = []
    for p in partidos:
        for _pk, _nk in [("away_pitcher_id", "away_pitcher"),
                          ("home_pitcher_id", "home_pitcher")]:
            pid  = p.get(_pk)
            name = p.get(_nk, "Por confirmar")
            if pid and name != "Por confirmar" and resumenes.get(pid):
                slate_items.append({"pitcher_id": pid, "Pitcher": name,
                                    "FIP": resumenes[pid]["FIP"]})
    slate_items.sort(key=lambda x: x["FIP"])
    rank_dia_lookup: dict = {it["pitcher_id"]: i + 1 for i, it in enumerate(slate_items)}
    n_rank_dia = len(slate_items)

    # ── Statcast 30 días — bateo ──────────────────────────────────────────────
    with st.spinner("Cargando Statcast 30 días para análisis de bateo..."):
        raw_30d = cargar_statcast_global(dias=30)

    today = date.today()
    if not raw_30d.empty and "game_date" in raw_30d.columns:
        _cutoff14 = today - timedelta(days=14)
        _cutoff16 = today - timedelta(days=16)
        _cutoff17 = today - timedelta(days=17)
        raw_14d   = raw_30d[raw_30d["game_date"] >= _cutoff14].copy()
        raw_16d   = raw_30d[raw_30d["game_date"] >= _cutoff16].copy()
        raw_17d   = raw_30d[raw_30d["game_date"] >= _cutoff17].copy()
    else:
        raw_14d = raw_16d = raw_17d = pd.DataFrame()

    # Batting by split
    batting_vs_R_14  = _batting_from_statcast(raw_14d,  p_throws="R")
    batting_vs_R_30  = _batting_from_statcast(raw_30d,  p_throws="R")
    batting_vs_L_30  = _batting_from_statcast(raw_30d,  p_throws="L")
    batting_vs_bp_16 = _batting_from_statcast(raw_16d,  min_inning=6)
    batting_vs_bp_30 = _batting_from_statcast(raw_30d,  min_inning=6)

    # ── RISP últimos 17 días — todos los equipos ──────────────────────────────
    batting_risp_17  = _batting_risp_from_statcast(raw_17d, min_pa=10)
    # Ranking liga completa por wOBA con RISP (mayor = mejor)
    _risp_sorted     = sorted(batting_risp_17.items(), key=lambda x: x[1]["wOBA"], reverse=True)
    risp_rank_liga: dict = {t: i + 1 for i, (t, _) in enumerate(_risp_sorted)}
    n_risp_liga = len(_risp_sorted)

    # ── Statcast 14 días — bullpen ────────────────────────────────────────────
    with st.spinner("Cargando Statcast 14 días para bullpen..."):
        raw_global = cargar_statcast_global(dias=14)

    ranking_fip: dict = {}
    for _t in MLB_TEAMS:
        _s = _bull_disp(raw_global, _t, fecha_sel)
        if _s["FIP"] is not None:
            ranking_fip[_t] = _s["FIP"]
    sorted_teams = sorted(ranking_fip, key=lambda t: ranking_fip[t])
    rank_global  = {t: i + 1 for i, t in enumerate(sorted_teams)}
    n_ranked     = len(sorted_teams)

    # ── Batting slate rankings ─────────────────────────────────────────────────
    # Para cada equipo del slate: batting vs la mano del pitcher que enfrentan hoy
    slate_bat_vs_starter: dict = {}
    slate_bat_vs_bull:    dict = {}
    for p in partidos:
        h = p["home_abbr"]; a = p["away_abbr"]
        h_pid = p.get("home_pitcher_id"); a_pid = p.get("away_pitcher_id")
        a_hand = pitcher_hands.get(a_pid, "R") if a_pid else "R"
        h_hand = pitcher_hands.get(h_pid, "R") if h_pid else "R"
        # Home batea vs away pitcher
        _hb = batting_vs_R_14.get(h, {}) if a_hand == "R" else batting_vs_L_30.get(h, {})
        if _hb:
            slate_bat_vs_starter[h] = {**_hb, "hand": a_hand,
                                        "period": "ult.14d" if a_hand == "R" else "ult.30d"}
        # Away batea vs home pitcher
        _ab = batting_vs_R_14.get(a, {}) if h_hand == "R" else batting_vs_L_30.get(a, {})
        if _ab:
            slate_bat_vs_starter[a] = {**_ab, "hand": h_hand,
                                        "period": "ult.14d" if h_hand == "R" else "ult.30d"}
        if batting_vs_bp_16.get(h): slate_bat_vs_bull[h] = batting_vs_bp_16[h]
        if batting_vs_bp_16.get(a): slate_bat_vs_bull[a] = batting_vs_bp_16[a]

    _sbs = sorted(slate_bat_vs_starter.items(), key=lambda x: x[1].get("wOBA", 0), reverse=True)
    slate_bat_rank:  dict = {t: i + 1 for i, (t, _) in enumerate(_sbs)}
    n_slate_bat = len(_sbs)
    _sbull = sorted(slate_bat_vs_bull.items(), key=lambda x: x[1].get("wOBA", 0), reverse=True)
    slate_bull_rank: dict = {t: i + 1 for i, (t, _) in enumerate(_sbull)}
    n_slate_bull = len(_sbull)

    # ═══════════════════════════════════════════════════════════════════════════
    # HELPERS DE DISPLAY
    # ═══════════════════════════════════════════════════════════════════════════

    def _woba_bar(woba_val: float):
        bar_color = "#28a745" if woba_val > 0.330 else ("#ffc107" if woba_val > 0.310 else "#dc3545")
        bar_pct   = max(5, min(100, int((woba_val - 0.240) / 0.110 * 100)))
        st.markdown(
            f"<div style='background:#e9ecef;border-radius:4px;height:6px;'>"
            f"<div style='width:{bar_pct}%;background:{bar_color};height:6px;border-radius:4px;'></div>"
            f"</div>", unsafe_allow_html=True)

    def _starter_card(col, pitcher_name: str, pitcher_id, team_name: str, side_label: str):
        with col:
            st.markdown(f"**{team_name} ({side_label})**")
            if pitcher_name == "Por confirmar":
                st.markdown("⚾ *Por confirmar*")
                return
            st.markdown(f"⚾ **{pitcher_name}**")
            if pitcher_id is None:
                st.markdown("*Sin ID*"); return

            hand     = pitcher_hands.get(pitcher_id, "R")
            hand_lbl = "Zurdo" if hand == "L" else "Derecho"
            st.markdown(f"*{hand_lbl}*")

            r_dia = rank_dia_lookup.get(pitcher_id)
            r_mes = rank_mes_lookup.get(pitcher_id)
            st.markdown(
                f"Rank hoy: **{'#'+str(r_dia)+'/'+str(n_rank_dia) if r_dia else '—'}**"
                f"  |  Rank mes: **{'#'+str(r_mes)+'/'+str(n_rank_mes) if r_mes else '—'}**"
            )

            df_log = gamelogs_60.get(pitcher_id, pd.DataFrame())
            res    = resumenes.get(pitcher_id, {})

            if df_log.empty or not res:
                st.info("Sin salidas registradas")
                return

            try:
                last_dt  = date.fromisoformat(str(df_log["Fecha"].iloc[0]))
                days_off = (fecha_sel - last_dt).days
                if   days_off >= 10: st.error(f"🔴 {days_off} días sin lanzar")
                elif days_off >= 7:  st.warning(f"⚠️ {days_off} días sin lanzar")
            except Exception:
                pass

            n = res["n"]
            st.markdown(
                f"Últ. **{n}** sal. — FIP `{res['FIP']}` | ERA `{res['ERA']}` | "
                f"ΔFIP `{res['ERA-FIP']}` | K% `{res['K%']}` | BB% `{res['BB%']}`"
            )
            # Columnas a mostrar; agregar FB mph si existe
            _sc = ["Fecha", "Rival", "IP", "K%", "BB%", "ERA", "FIP", "ERA-FIP"]
            if "FB mph" in df_log.columns:
                _sc = ["Fecha", "Rival", "IP", "FB mph", "K%", "BB%", "ERA", "FIP", "ERA-FIP"]
            st.dataframe(df_log[_sc], use_container_width=True, hide_index=True)

            # ── Texto del artículo externo ────────────────────────────────
            _art_txt = _buscar_pitcher_en_articulo(pitcher_name, _article_data)
            if _art_txt:
                st.markdown(
                    "<div style='background:#f0f4ff;border-left:4px solid #4a7fd4;"
                    "padding:10px 14px;border-radius:0 6px 6px 0;margin-top:8px;'>"
                    "<span style='font-size:0.75rem;font-weight:600;color:#4a7fd4;"
                    "text-transform:uppercase;letter-spacing:0.05em;'>📰 Pitcher List</span>",
                    unsafe_allow_html=True,
                )
                for _line in _art_txt.split("\n\n"):
                    if _line.strip():
                        st.markdown(
                            f"<p style='font-size:0.85rem;margin:6px 0 0 0;"
                            f"color:#1a1a2e;'>{_line.strip()}</p>",
                            unsafe_allow_html=True,
                        )
                st.markdown("</div>", unsafe_allow_html=True)

    def _bat_card(col, team: str, team_name: str, bat_d: dict,
                  s_rank, n_s, period: str, vs_hand: str):
        with col:
            vs_lbl = "RHP" if vs_hand == "R" else "LHP"
            st.markdown(f"**{team_name}** batea vs **{vs_lbl}** *({period})*")
            if bat_d:
                rank_str = f"#**{s_rank}**/{n_s}" if s_rank else "—"
                st.markdown(
                    f"wOBA `{bat_d['wOBA']}` | wRC+ `{bat_d['wRC+']}` | "
                    f"PA `{bat_d['PA']}` | Rank slate: {rank_str}"
                )
                _woba_bar(bat_d["wOBA"])
            else:
                st.caption("Sin datos de bateo")

    def _bull_card(col, name: str, s: dict, rank_str: str):
        with col:
            if s["FIP"] is not None:
                fip_val = s["FIP"]
                bar_col = "#28a745" if fip_val < 3.50 else ("#ffc107" if fip_val < 4.20 else "#dc3545")
                bar_pct = max(5, min(100, int((5.5 - fip_val) / 3.0 * 100)))
                st.markdown(
                    f"**{name}** — Rank: **{rank_str}**  \n"
                    f"FIP `{fip_val}` | K% `{s['K%']}` | BB% `{s['BB%']}` | wOBA `{s['wOBA']}`  \n"
                    f"Disponibles: **{s['n_disp']}/{s['n_total']}**"
                )
                st.markdown(
                    f"<div style='background:#e9ecef;border-radius:4px;height:8px;'>"
                    f"<div style='width:{bar_pct}%;background:{bar_col};height:8px;border-radius:4px;'></div>"
                    f"</div>", unsafe_allow_html=True)
            else:
                st.caption(f"{name}: sin datos de bullpen (sin Statcast reciente)")

    # ═══════════════════════════════════════════════════════════════════════════
    # ENCABEZADO
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown(f"### {fecha_sel.strftime('%A %d %b %Y')} — {len(partidos)} partidos")
    st.caption(
        "Iniciadores: ults. salidas disponibles | Bateo: Statcast 14d vs RHP, 30d vs LHP | "
        "Bullpen: disp. Statcast 14d, mín. 2 aps. | Bateo vs BP: ult. 16d | RISP: ult. 17d"
    )

    # ── Precargar SOS de todos los equipos del slate ─────────────────────────
    with st.spinner("Cargando Strength of Schedule..."):
        _sos_tids: set = set()
        for _pp in partidos:
            for _tk in ("home_abbr", "away_abbr"):
                _tid_tmp = MLB_TEAM_IDS.get(_pp[_tk])
                if _tid_tmp:
                    _sos_tids.add(_tid_tmp)
        _sos_map: dict = {_t: cargar_sos_equipo(_t) for _t in _sos_tids}

    # ═══════════════════════════════════════════════════════════════════════════
    # EXPANDER POR PARTIDO
    # ═══════════════════════════════════════════════════════════════════════════
    for p in partidos:
        h = p["home_abbr"];  a = p["away_abbr"]
        h_name = p["home_name"]; a_name = p["away_name"]
        h_pid = p.get("home_pitcher_id"); a_pid = p.get("away_pitcher_id")
        a_hand = pitcher_hands.get(a_pid, "R") if a_pid else "R"
        h_hand = pitcher_hands.get(h_pid, "R") if h_pid else "R"

        sh = _bull_disp(raw_global, h, fecha_sel)
        sa = _bull_disp(raw_global, a, fecha_sel)
        rh = rank_global.get(h); ra = rank_global.get(a)

        if sh["FIP"] and sa["FIP"]:
            _diff = sh["FIP"] - sa["FIP"]
            if   _diff < -0.30: _ventaja = f"✅ Ventaja bullpen: **{h_name}**"; _cv = "#d4edda"
            elif _diff >  0.30: _ventaja = f"✅ Ventaja bullpen: **{a_name}**"; _cv = "#d4edda"
            else:                _ventaja = "➡️ Bullpens similares";             _cv = "#fff3cd"
        else:
            _ventaja = "⚠️ Sin datos suficientes de bullpen"; _cv = "#f8f9fa"

        # batting context para este partido
        _h_bat = batting_vs_R_14.get(h, {}) if a_hand == "R" else batting_vs_L_30.get(h, {})
        _a_bat = batting_vs_R_14.get(a, {}) if h_hand == "R" else batting_vs_L_30.get(a, {})
        _h_per = "ult.14d" if a_hand == "R" else "ult.30d"
        _a_per = "ult.14d" if h_hand == "R" else "ult.30d"
        _h_bp  = batting_vs_bp_16.get(h, {})
        _a_bp  = batting_vs_bp_16.get(a, {})

        # Récords de los equipos
        _h_tid = MLB_TEAM_IDS.get(h); _a_tid = MLB_TEAM_IDS.get(a)
        _rec_h = cargar_records_equipo(_h_tid) if _h_tid else {}
        _rec_a = cargar_records_equipo(_a_tid) if _a_tid else {}
        _h2h   = cargar_h2h(_h_tid, _a_tid) if _h_tid and _a_tid else "—"
        # Record vs mano del pitcher que enfrentan hoy
        _rvh_h = cargar_record_vs_hand(_h_tid, a_hand) if _h_tid else "—"  # home vs away pitcher hand
        _rvh_a = cargar_record_vs_hand(_a_tid, h_hand) if _a_tid else "—"  # away vs home pitcher hand
        # SOS
        _sos_h = _sos_map.get(_h_tid, {})
        _sos_a = _sos_map.get(_a_tid, {})
        # Día de la semana del partido
        _wday  = fecha_sel.weekday()
        _wday_names = {0:"Lun",1:"Mar",2:"Mié",3:"Jue",4:"Vie",5:"Sáb",6:"Dom"}
        _wday_lbl  = _wday_names.get(_wday, "—")
        _wd_rec_h  = (_rec_h.get("weekday") or {}).get(_wday, "—")
        _wd_rec_a  = (_rec_a.get("weekday") or {}).get(_wday, "—")

        # Clima del partido (solo estadios abiertos)
        _clima = cargar_clima_partido(h, p.get("game_date_utc", ""))

        with st.expander(
            f"**{a_name}** @ **{h_name}**  —  {p['hora']}  |  {p['venue']}",
            expanded=False,
        ):
            # ── Clima ────────────────────────────────────────────────────────
            if _clima:
                _rain_icon = _clima["rain_emoji"]
                _wind_icon = _clima["wind_emoji"]
                st.markdown(
                    f"{_rain_icon} **{_clima['temp_f']}°F / {_clima['temp_c']}°C** · "
                    f"Humedad: **{_clima['humidity']}%** · "
                    f"Lluvia: **{_clima['precip_prob']}%** · "
                    f"{_wind_icon} Viento: **{_clima['wind_kph']} km/h** → *{_clima['wind_rel']}*"
                )
            elif h in DOMED_STADIUMS:
                st.caption("🏟️ Estadio techado — sin efecto de viento")

            # ── Récords de equipo ────────────────────────────────────────────
            st.markdown("#### 📋 Récords & SOS")
            _cr1, _cr2 = st.columns(2)
            for _col, _tname, _rec, _rvh, _hand_lbl, _wdrec, _sos in [
                (_cr1, a_name, _rec_a, _rvh_a, "RHP" if h_hand == "R" else "LHP", _wd_rec_a, _sos_a),
                (_cr2, h_name, _rec_h, _rvh_h, "RHP" if a_hand == "R" else "LHP", _wd_rec_h, _sos_h),
            ]:
                with _col:
                    _s   = _rec.get("season", "—")
                    _l10 = _rec.get("last10", "—")
                    _h10 = _rec.get("home10", "—")
                    _a10 = _rec.get("away10", "—")
                    # SOS labels
                    _s30v = _sos.get("sos_30d")
                    _s7v  = _sos.get("sos_7d")
                    _s14v = _sos.get("sos_14d")
                    _g30  = _sos.get("g_30d", 0)
                    _g7   = _sos.get("g_7d",  0)
                    _g14  = _sos.get("g_14d", 0)
                    _rv5  = _sos.get("rec_vs_500", "—")
                    def _sos_label(v):
                        if v is None: return "—"
                        s = f"{v:.3f}"
                        if v >= 0.520:   return f"{s} 🔴"
                        elif v >= 0.500: return f"{s} 🟡"
                        else:            return f"{s} 🟢"
                    st.markdown(
                        f"**{_tname}**  \n"
                        f"Temporada: `{_s}` | Últ.10: `{_l10}`  \n"
                        f"Casa(10): `{_h10}` | Visita(10): `{_a10}`  \n"
                        f"Vs {_hand_lbl}: `{_rvh}` | {_wday_lbl}: `{_wdrec}`  \n"
                        f"SOS-30d ({_g30}G): **{_sos_label(_s30v)}** | "
                        f"Vs .500+ (46d): `{_rv5}`  \n"
                        f"SOS fut-7d ({_g7}G): **{_sos_label(_s7v)}** | "
                        f"SOS fut-14d ({_g14}G): **{_sos_label(_s14v)}**"
                    )
            st.caption(f"H2H temporada ({a_name} vs {h_name}): **{_h2h}** (récord del local) | "
                       f"SOS: 🟢 <.500 fácil | 🟡 .500-.519 | 🔴 ≥.520 difícil")

            st.divider()

            # ── Iniciadores ─────────────────────────────────────────────────
            st.markdown("#### ⚾ Pitchers Iniciadores")
            _ci1, _ci2 = st.columns(2)
            _starter_card(_ci1, p["away_pitcher"], a_pid, a_name, "Visitante")
            _starter_card(_ci2, p["home_pitcher"], h_pid, h_name, "Local")

            st.divider()

            # ── Bateo vs Starter (mano específica) ──────────────────────────
            st.markdown("#### 📊 Bateo vs Pitcher Inicial")
            _cb1, _cb2 = st.columns(2)
            # Away batea vs home pitcher (h_hand)
            _bat_card(_cb1, a, a_name, _a_bat,
                      slate_bat_rank.get(a), n_slate_bat, _a_per, h_hand)
            # Home batea vs away pitcher (a_hand)
            _bat_card(_cb2, h, h_name, _h_bat,
                      slate_bat_rank.get(h), n_slate_bat, _h_per, a_hand)

            st.divider()

            # ── Bateo vs Bullpen (inn 6+) ────────────────────────────────────
            st.markdown("#### 🛡️ Bateo vs Bullpen (inn. 6+, ult. 16d)")
            _cbp1, _cbp2 = st.columns(2)
            for _col, _team, _tname, _bpd in [
                (_cbp1, a, a_name, _a_bp), (_cbp2, h, h_name, _h_bp)
            ]:
                with _col:
                    st.markdown(f"**{_tname}**")
                    if _bpd:
                        _rk = slate_bull_rank.get(_team)
                        st.markdown(
                            f"wOBA `{_bpd['wOBA']}` | wRC+ `{_bpd['wRC+']}` | "
                            f"PA `{_bpd['PA']}` | Rank slate: {'#**'+str(_rk)+'**/'+str(n_slate_bull) if _rk else '—'}"
                        )
                        _woba_bar(_bpd["wOBA"])
                    else:
                        st.caption("Sin datos")

            st.divider()

            # ── Bullpen disponible ───────────────────────────────────────────
            st.markdown("#### 🔥 Bullpen Disponible")
            _cb3, _cb4 = st.columns(2)
            _bull_card(_cb3, a_name, sa, f"#{ra}/{n_ranked}" if ra else "—")
            _bull_card(_cb4, h_name, sh, f"#{rh}/{n_ranked}" if rh else "—")
            st.markdown(
                f"<div style='background:{_cv};padding:8px 14px;border-radius:6px;"
                f"margin-top:8px;font-size:0.9rem;'>{_ventaja}</div>",
                unsafe_allow_html=True,
            )

            st.divider()

            # ── Lineup confirmado ────────────────────────────────────────────
            _gk = p.get("game_pk")
            if _gk:
                _lineup = cargar_lineup_partido(_gk, cache_bucket=_lineup_cache_bucket())
                _lh = _lineup.get("home", [])
                _la = _lineup.get("away", [])
                if _lh or _la:
                    st.markdown("#### 📋 Lineup Confirmado")
                    _cl1, _cl2 = st.columns(2)
                    for _col, _tname, _lin in [(_cl1, a_name, _la), (_cl2, h_name, _lh)]:
                        with _col:
                            st.markdown(f"**{_tname}**")
                            if _lin:
                                _df_lin = pd.DataFrame(_lin)
                                _cols = ["order", "nombre", "pos", "wOBA", "wRC+"]
                                _df_lin = _df_lin[[c for c in _cols if c in _df_lin.columns]]
                                _df_lin.columns = ["#", "Jugador", "Pos", "wOBA", "wRC+"][:len(_df_lin.columns)]
                                st.dataframe(_df_lin.set_index("#"), use_container_width=True, hide_index=False)
                            else:
                                st.caption("Lineup no disponible aún")
                    st.divider()

            # ── Bateadores calientes ─────────────────────────────────────────
            st.markdown("#### 🌡️ Bateadores Calientes — ult. 14 días")
            _ch1, _ch2 = st.columns(2)
            for _col, _team, _tname in [(_ch1, a, a_name), (_ch2, h, h_name)]:
                with _col:
                    st.markdown(f"**{_tname}**")
                    _tid  = MLB_TEAM_IDS.get(_team)
                    _hot  = cargar_hot_hitters(_tid) if _tid else []
                    if _hot:
                        _df_hot = pd.DataFrame(_hot)[["Bateador", "PA", "wOBA", "OPS", "HR"]]
                        st.dataframe(_df_hot.set_index("Bateador"),
                                     use_container_width=True)
                    else:
                        st.caption("Sin datos")

            st.divider()

            # ── Fuego en el bat: RISP ────────────────────────────────────────
            st.markdown("#### 🔥 Fuego en el Bat — Bateo con RISP (ult. 17d)")
            _cr1, _cr2 = st.columns(2)
            for _col, _team, _tname in [(_cr1, a, a_name), (_cr2, h, h_name)]:
                with _col:
                    _rd = batting_risp_17.get(_team, {})
                    _rk = risp_rank_liga.get(_team)
                    st.markdown(f"**{_tname}**")
                    if _rd:
                        _rk_str = f"#{_rk}/{n_risp_liga}" if _rk else "—"
                        if _rk and _rk <= 8:
                            _rk_badge = f"🔥 #{_rk} (Top 8)"
                        elif _rk and _rk <= 15:
                            _rk_badge = f"✅ #{_rk} (Top 15)"
                        elif _rk and _rk <= 25:
                            _rk_badge = f"🟡 #{_rk}"
                        else:
                            _rk_badge = f"🔴 #{_rk} (Bottom 5)"
                        st.markdown(
                            f"wOBA `{_rd['wOBA']}` | AVG `{_rd['AVG']}` | "
                            f"PA `{_rd['PA']}` | Liga: **{_rk_badge}**"
                        )
                        _woba_bar(_rd["wOBA"])
                    else:
                        st.caption("Sin datos RISP")

            st.divider()

            # ── WAR líderes ──────────────────────────────────────────────────
            st.markdown("#### 🏆 Líderes WAR — temporada")
            _cw1, _cw2 = st.columns(2)
            for _col, _team, _tname in [(_cw1, a, a_name), (_cw2, h, h_name)]:
                with _col:
                    st.markdown(f"**{_tname}**")
                    _war = cargar_war_equipo(_team)
                    if _war:
                        st.dataframe(pd.DataFrame(_war).set_index("Jugador"),
                                     use_container_width=True)
                    else:
                        st.caption("Sin datos WAR (temporada sin iniciar o FanGraphs no disponible)")

    # ═══════════════════════════════════════════════════════════════════════════
    # TABLAS DE RANKING (debajo de todos los partidos)
    # ═══════════════════════════════════════════════════════════════════════════

    # ── Ranking slate: bateo vs starter ───────────────────────────────────────
    if _sbs:
        st.divider()
        st.markdown("### 📊 Ranking Slate — Bateo vs Pitcher Inicial (mano específica)")
        st.caption("wOBA vs RHP (14d) o vs LHP (30d) según la mano del pitcher que enfrentan hoy.")
        _rows_sb = []
        for _i, (_t, _d) in enumerate(_sbs):
            _rows_sb.append({
                "#": _i + 1,
                "Equipo": TEAM_NAMES.get(_t, _t),
                "Vs":     "RHP" if _d.get("hand") == "R" else "LHP",
                "Periodo": _d.get("period", "—"),
                "wOBA":   _d["wOBA"],
                "wRC+":   _d["wRC+"],
                "PA":     _d["PA"],
            })
        st.dataframe(pd.DataFrame(_rows_sb).set_index("#"), use_container_width=True)

    # ── Ranking slate: bateo vs bullpen ───────────────────────────────────────
    if _sbull:
        st.divider()
        st.markdown("### 🛡️ Ranking Slate — Bateo vs Bullpen (inn. 6+, ult. 16d)")
        _rows_bul = [
            {"#": _i + 1, "Equipo": TEAM_NAMES.get(_t, _t),
             "wOBA": _d["wOBA"], "wRC+": _d["wRC+"], "PA": _d["PA"]}
            for _i, (_t, _d) in enumerate(_sbull)
        ]
        st.dataframe(pd.DataFrame(_rows_bul).set_index("#"), use_container_width=True)

    # ── Ranking liga 30d: vs RHP ──────────────────────────────────────────────
    st.divider()
    st.markdown("### 🌎 Ranking Liga — Bateo vs RHP (últimos 30 días)")
    if batting_vs_R_30:
        _rows_R = sorted(batting_vs_R_30.items(), key=lambda x: x[1]["wOBA"], reverse=True)
        st.dataframe(
            pd.DataFrame([
                {"#": _i+1, "Equipo": TEAM_NAMES.get(_t, _t),
                 "wOBA": _d["wOBA"], "wRC+": _d["wRC+"], "PA": _d["PA"]}
                for _i, (_t, _d) in enumerate(_rows_R)
            ]).set_index("#"), use_container_width=True)
    else:
        st.info("Sin datos suficientes (Statcast puede no tener datos aún).")

    # ── Ranking liga 30d: vs LHP ──────────────────────────────────────────────
    st.markdown("### 🌎 Ranking Liga — Bateo vs LHP (últimos 30 días)")
    if batting_vs_L_30:
        _rows_L = sorted(batting_vs_L_30.items(), key=lambda x: x[1]["wOBA"], reverse=True)
        st.dataframe(
            pd.DataFrame([
                {"#": _i+1, "Equipo": TEAM_NAMES.get(_t, _t),
                 "wOBA": _d["wOBA"], "wRC+": _d["wRC+"], "PA": _d["PA"]}
                for _i, (_t, _d) in enumerate(_rows_L)
            ]).set_index("#"), use_container_width=True)
    else:
        st.info("Sin datos suficientes.")

    # ── Ranking liga 30d: vs bullpen ──────────────────────────────────────────
    st.markdown("### 🌎 Ranking Liga — Bateo vs Bullpen (inn. 6+, últimos 30 días)")
    if batting_vs_bp_30:
        _rows_bp = sorted(batting_vs_bp_30.items(), key=lambda x: x[1]["wOBA"], reverse=True)
        st.dataframe(
            pd.DataFrame([
                {"#": _i+1, "Equipo": TEAM_NAMES.get(_t, _t),
                 "wOBA": _d["wOBA"], "wRC+": _d["wRC+"], "PA": _d["PA"]}
                for _i, (_t, _d) in enumerate(_rows_bp)
            ]).set_index("#"), use_container_width=True)
    else:
        st.info("Sin datos suficientes.")

    # ── Ranking diario de iniciadores ─────────────────────────────────────────
    if slate_items:
        st.divider()
        st.markdown("### Ranking de iniciadores — slate de hoy")
        st.caption("Ordenado por FIP de últimas 4 salidas disponibles.")
        _slate_rows = []
        for _i, _it in enumerate(slate_items):
            _res = resumenes[_it["pitcher_id"]]
            _rm  = rank_mes_lookup.get(_it["pitcher_id"])
            _velo = pitcher_velos.get(_it["pitcher_id"])
            _hand = pitcher_hands.get(_it["pitcher_id"], "R")
            _slate_rows.append({
                "#":        _i + 1,
                "Pitcher":  _it["Pitcher"],
                "Mano":     "L" if _hand == "L" else "R",
                "FB mph":   _velo or "—",
                "GS":       _res["n"],
                "FIP":      _res["FIP"],
                "ERA":      _res["ERA"],
                "ERA-FIP":  _res["ERA-FIP"],
                "K%":       _res["K%"],
                "BB%":      _res["BB%"],
                "Rank mes": f"#{_rm}/{n_rank_mes}" if _rm else "—",
            })
        st.dataframe(pd.DataFrame(_slate_rows).set_index("#"), use_container_width=True)

    # ── Ranking mensual de iniciadores ────────────────────────────────────────
    st.divider()
    st.markdown("### Ranking mensual de iniciadores — toda la liga (últimos 30 días)")
    st.caption("Mín. 2 GS en 30 días Y 2 GS en últimos 14 días. Ordenado por FIP.")
    if df_rank_mes.empty:
        st.info("Sin datos (temporada no iniciada o insuficientes lanzadores calificados).")
    else:
        _show_mes = df_rank_mes[["Rank_mes", "Pitcher", "Team", "GS", "IP",
                                  "K%", "BB%", "ERA", "FIP", "ERA-FIP"]].copy()
        st.dataframe(_show_mes.set_index("Rank_mes"), use_container_width=True)

    # ── Resumen rápido del día ────────────────────────────────────────────────
    st.divider()
    st.markdown("### Resumen del día")
    _sum_rows = []
    for p in partidos:
        h = p["home_abbr"]; a = p["away_abbr"]
        _sh = _bull_disp(raw_global, h, fecha_sel)
        _sa = _bull_disp(raw_global, a, fecha_sel)
        _rh = rank_global.get(h); _ra = rank_global.get(a)
        _h_pid = p.get("home_pitcher_id"); _a_pid = p.get("away_pitcher_id")
        _rd_h = rank_dia_lookup.get(_h_pid); _rd_a = rank_dia_lookup.get(_a_pid)
        _a_hand_s = "L" if pitcher_hands.get(_a_pid, "R") == "L" else "R"
        _h_hand_s = "L" if pitcher_hands.get(_h_pid, "R") == "L" else "R"
        if _sh["FIP"] and _sa["FIP"]:
            _vent = (TEAM_NAMES.get(h, h) if _sh["FIP"] < _sa["FIP"] - 0.30
                     else (TEAM_NAMES.get(a, a) if _sa["FIP"] < _sh["FIP"] - 0.30 else "Similar"))
        else:
            _vent = "Sin datos"
        _sum_rows.append({
            "Visitante":    TEAM_NAMES.get(a, a),
            "Starter Vis.": p["away_pitcher"],
            "Mano":         _h_hand_s,
            "FB mph":       pitcher_velos.get(_a_pid) or "—",
            "Rank día Vis.":f"#{_rd_a}/{n_rank_dia}" if _rd_a else "—",
            "FIP Bull.Vis.":_sa["FIP"] or "—",
            "Local":        TEAM_NAMES.get(h, h),
            "Starter Loc.": p["home_pitcher"],
            "Mano ":        _a_hand_s,
            "FB mph ":      pitcher_velos.get(_h_pid) or "—",
            "Rank día Loc.":f"#{_rd_h}/{n_rank_dia}" if _rd_h else "—",
            "FIP Bull.Loc.":_sh["FIP"] or "—",
            "Ventaja Bull.":_vent,
            "Hora":         p["hora"],
        })
    if _sum_rows:
        st.dataframe(pd.DataFrame(_sum_rows).set_index("Visitante"),
                     use_container_width=True)


# =============================================================================
# PRONÓSTICO — Scoring Heurístico de Ventaja
# =============================================================================

def calcular_ventaja_partido(partido: dict, resumenes: dict, raw_global,
                             batting_vs_R_14: dict, batting_vs_L_30: dict,
                             batting_vs_bp_14: dict, rank_global: dict,
                             rank_dia_lookup: dict, n_rank_dia: int,
                             pitcher_hands: dict, records: dict,
                             h2h: str, clima: dict | None,
                             batting_risp: dict = None,
                             risp_rank: dict = None,
                             pitcher_rec: dict = None) -> dict:
    """
    Calcula puntuación heurística para cada equipo en el partido.
    Retorna dict con puntaje_local, puntaje_visita, factores (lista de strings).
    """
    if batting_risp is None:
        batting_risp = {}
    if risp_rank is None:
        risp_rank = {}
    if pitcher_rec is None:
        pitcher_rec = {}
    home  = partido["home_abbr"]
    away  = partido["away_abbr"]
    h_pid = partido.get("home_pitcher_id")
    a_pid = partido.get("away_pitcher_id")
    h_tid = MLB_TEAM_IDS.get(home)
    a_tid = MLB_TEAM_IDS.get(away)

    pts_home = 0.0
    pts_away = 0.0
    factores = []

    # ── Factor 1: FIP iniciador (3 pts para el equipo que ENFRENTA al peor pitcher) ──
    res_h = resumenes.get(h_pid, {})
    res_a = resumenes.get(a_pid, {})
    fip_h = res_h.get("FIP")  # FIP del starter local
    fip_a = res_a.get("FIP")  # FIP del starter visitante
    if fip_h is not None and fip_a is not None:
        diff = abs(fip_h - fip_a)
        if diff >= 2.5:
            pts = 2.5
        elif diff >= 2.0:
            pts = 2.2
        elif diff > 1.5:
            pts = 1.5
        elif diff > 1.0:
            pts = 1.0
        else:
            pts = 0.5
        if fip_h > fip_a:  # starter local es PEOR → visitante gana puntos
            pts_away += pts
            factores.append(f"✅ Visitante: FIP iniciadores ({fip_h:.2f} vs {fip_a:.2f}, dif {diff:.2f}) +{pts}pt")
        else:
            pts_home += pts
            factores.append(f"✅ Local: FIP iniciadores ({fip_h:.2f} vs {fip_a:.2f}, dif {diff:.2f}) +{pts}pt")
    else:
        factores.append("❓ FIP iniciadores: sin datos")

    # ── Factor 2: ERA-FIP regresión (1 pt si ERA > FIP → probable caída) ──
    ef_h = res_h.get("ERA_FIP")
    ef_a = res_a.get("ERA_FIP")
    # ERA_FIP = ERA - FIP; si positivo, pitcher tiene suerte negativa → esperamos regresión (mejor)
    # Si ERA_FIP > 0.5 → el equipo visitante (batting) se beneficia del starter local que regresará
    if ef_h is not None and ef_h > 0.5:
        pts_away += 0.5
        factores.append(f"✅ Visitante: starter local ERA-FIP={ef_h:.2f} (regresión esperada) +0.5pt")
    elif ef_a is not None and ef_a > 0.5:
        pts_home += 0.5
        factores.append(f"✅ Local: starter visitante ERA-FIP={ef_a:.2f} (regresión esperada) +0.5pt")
    else:
        factores.append("🟰 ERA-FIP: sin señal clara de regresión")

    # ── Factor 3: Rust del starter (días sin lanzar en la temporada actual) ──
    def _rust_penalty(last_dt, game_dt) -> tuple[float, str]:
        """Retorna (puntos_penalidad, descripcion). Solo dentro de la misma temporada."""
        if last_dt is None or game_dt is None:
            return 0.0, "sin datos de fecha"
        # Solo misma temporada (mismo año)
        if last_dt.year != game_dt.year:
            return 0.0, "última salida en temporada anterior — no aplica"
        days = (game_dt - last_dt).days
        if days > 30:
            return 0.85, f"{days}d sin lanzar (>30d) — óxido severo"
        if days >= 17:
            return 0.45, f"{days}d sin lanzar (17-30d) — muy oxidado"
        if days >= 13:
            return 0.3,  f"{days}d sin lanzar (13-16d) — oxidado"
        if days >= 7:
            return 0.2,  f"{days}d sin lanzar (7-12d) — algo oxidado"
        return 0.0, f"{days}d — descanso normal"

    try:
        _game_dt_rust = date.fromisoformat(partido.get("game_date_utc", "")[:10])
    except Exception:
        _game_dt_rust = date.today()

    _last_h = res_h.get("last_date")
    _last_a = res_a.get("last_date")
    _rust_pen_h, _rust_desc_h = _rust_penalty(_last_h, _game_dt_rust)
    _rust_pen_a, _rust_desc_a = _rust_penalty(_last_a, _game_dt_rust)

    if _rust_pen_h > 0:
        pts_away += _rust_pen_h
        factores.append(f"🦾 Visitante: starter local con óxido — {_rust_desc_h} +{_rust_pen_h}pt")
    elif _rust_desc_h != "sin datos de fecha":
        factores.append(f"✅ Starter local: {_rust_desc_h}")

    if _rust_pen_a > 0:
        pts_home += _rust_pen_a
        factores.append(f"🦾 Local: starter visitante con óxido — {_rust_desc_a} +{_rust_pen_a}pt")
    elif _rust_desc_a != "sin datos de fecha":
        factores.append(f"✅ Starter visitante: {_rust_desc_a}")

    # ── Factor 4: Bateo vs mano del pitcher (wRC+) ──
    # Cada equipo recibe pts absolutos según su wRC+: (wRC+ - 100) / 10
    # Promedio liga = 100 = 0pts. +10 wRC+ = +1 carrera = +1pt. Cap: ±2.5
    h_hand = pitcher_hands.get(h_pid, "R")
    a_hand = pitcher_hands.get(a_pid, "R")
    bat_src_away = batting_vs_R_14 if h_hand == "R" else batting_vs_L_30
    bat_src_home = batting_vs_R_14 if a_hand == "R" else batting_vs_L_30

    def _wrc_pts(wrc):
        if wrc is None: return None
        return round(max(-2.5, min(2.5, (wrc - 100) / 10)), 2)

    wrc_away_vs = (bat_src_away.get(away) or {}).get("wRC+")
    wrc_home_vs = (bat_src_home.get(home) or {}).get("wRC+")
    vs_lbl_a = "RHP" if h_hand == "R" else "LHP"
    vs_lbl_h = "RHP" if a_hand == "R" else "LHP"

    _p4a = _wrc_pts(wrc_away_vs)
    _p4h = _wrc_pts(wrc_home_vs)
    if _p4a is not None:
        pts_away += _p4a
        _ic = "✅" if _p4a > 0 else ("🔴" if _p4a < 0 else "🟰")
        factores.append(f"{_ic} Visitante: wRC+ vs {vs_lbl_a} = {wrc_away_vs} ({_p4a:+.2f}pt)")
    else:
        factores.append(f"❓ Visitante: wRC+ vs {vs_lbl_a}: sin datos")
    if _p4h is not None:
        pts_home += _p4h
        _ic = "✅" if _p4h > 0 else ("🔴" if _p4h < 0 else "🟰")
        factores.append(f"{_ic} Local: wRC+ vs {vs_lbl_h} = {wrc_home_vs} ({_p4h:+.2f}pt)")
    else:
        factores.append(f"❓ Local: wRC+ vs {vs_lbl_h}: sin datos")

    # ── Factor 5: FIP Bullpen (2 pts + 0.5 bonus si diff muy grande) ──
    _game_fecha = date.today()
    try:
        _gdt_str = partido.get("game_date_utc", "")
        if _gdt_str:
            _game_fecha = datetime.fromisoformat(_gdt_str.replace("Z", "+00:00")).date()
    except Exception:
        pass
    bull_h = _bull_disp(raw_global, home, _game_fecha)
    bull_a = _bull_disp(raw_global, away, _game_fecha)
    bfip_h = bull_h.get("FIP")
    bfip_a = bull_a.get("FIP")
    if bfip_h is not None and bfip_a is not None:
        bdiff = abs(bfip_h - bfip_a)
        if bdiff >= 2.0:
            pts = 1.8
        elif bdiff > 1.5:
            pts = 1.5
        elif bdiff > 1.0:
            pts = 1.0
        else:
            pts = 0.5
        if bfip_h < bfip_a:  # bullpen local mejor
            pts_home += pts
            factores.append(f"✅ Local: bullpen FIP ({bfip_h:.2f} vs {bfip_a:.2f}, dif {bdiff:.2f}) +{pts}pt")
        else:
            pts_away += pts
            factores.append(f"✅ Visitante: bullpen FIP ({bfip_a:.2f} vs {bfip_h:.2f}, dif {bdiff:.2f}) +{pts}pt")
    else:
        factores.append("❓ FIP Bullpen: sin datos")

    # ── Factor 5b: Degradación del bullpen (claves no disponibles) ──
    # Compara FIP del bullpen completo vs FIP de los disponibles
    # Si la diferencia es grande, los mejores relevistas están fuera
    def _fip_completo(raw_g, team):
        df_t = _extraer_apariciones_equipo(raw_g, team)
        if df_t.empty: return None
        df_t = _filtrar_calificados(df_t, min_juegos=1)
        if df_t.empty or df_t["IP"].sum() == 0: return None
        return _stats_agregadas(df_t).get("FIP")

    fip_full_h = _fip_completo(raw_global, home)
    fip_full_a = _fip_completo(raw_global, away)
    fip_disp_h = bull_h.get("FIP")
    fip_disp_a = bull_a.get("FIP")

    for _side, _fip_full, _fip_disp, _team_name, _pts_target in [
        ("home", fip_full_h, fip_disp_h, home, "away"),
        ("away", fip_full_a, fip_disp_a, away, "home"),
    ]:
        if _fip_full is not None and _fip_disp is not None:
            _deg = _fip_disp - _fip_full  # positivo = bullpen disponible peor que el completo
            if _deg >= 1.99:
                _dp = 1.5
            elif _deg >= 1.0:
                _dp = 1.0
            elif _deg > 0.5:
                _dp = 0.5
            elif _deg > 0.3:
                _dp = 0.3
            else:
                _dp = 0.0
            _side_lbl = "Local" if _side == "home" else "Visitante"
            _rival_lbl = "Visitante" if _side == "home" else "Local"
            if _dp > 0:
                if _pts_target == "away":
                    pts_away += _dp
                else:
                    pts_home += _dp
                factores.append(
                    f"⚠️ {_rival_lbl}: bullpen {_side_lbl} degradado "
                    f"(FIP disp {_fip_disp:.2f} vs completo {_fip_full:.2f}, Δ{_deg:.2f}) +{_dp}pt"
                )
            else:
                factores.append(
                    f"🟢 Bullpen {_side_lbl}: sin degradación significativa "
                    f"(FIP disp {_fip_disp:.2f} vs completo {_fip_full:.2f})"
                )

    # ── Factor 6: Bateo vs Bullpen inn6+ (wRC+) ──
    wrc_away_bp = (batting_vs_bp_14.get(away) or {}).get("wRC+")
    wrc_home_bp = (batting_vs_bp_14.get(home) or {}).get("wRC+")
    _p6a = _wrc_pts(wrc_away_bp)
    _p6h = _wrc_pts(wrc_home_bp)
    if _p6a is not None:
        pts_away += _p6a
        _ic = "✅" if _p6a > 0 else ("🔴" if _p6a < 0 else "🟰")
        factores.append(f"{_ic} Visitante: wRC+ vs bullpen = {wrc_away_bp} ({_p6a:+.2f}pt)")
    else:
        factores.append("❓ Visitante: wRC+ vs bullpen: sin datos")
    if _p6h is not None:
        pts_home += _p6h
        _ic = "✅" if _p6h > 0 else ("🔴" if _p6h < 0 else "🟰")
        factores.append(f"{_ic} Local: wRC+ vs bullpen = {wrc_home_bp} ({_p6h:+.2f}pt)")
    else:
        factores.append("❓ Local: wRC+ vs bullpen: sin datos")

    # ── Factor 7: Últimos 10 general (2 pts) ──
    rec_h = records.get(home, {})
    rec_a = records.get(away, {})
    def _parse_rec(s):
        try: w, l = s.split("-"); return int(w), int(l)
        except: return None, None
    hw, hl = _parse_rec(rec_h.get("last10", "—"))
    aw, al = _parse_rec(rec_a.get("last10", "—"))
    if hw is not None and aw is not None:
        diff7 = abs(hw - aw)
        if diff7 > 8:
            pts = 1.0
        elif diff7 >= 6:
            pts = 0.7
        elif diff7 >= 3:
            pts = 0.5
        else:
            pts = 0.0
        if pts > 0:
            if hw > aw:
                pts_home += pts
                factores.append(f"✅ Local: últ.10 {hw}-{hl} vs {aw}-{al} +{pts}pt")
            else:
                pts_away += pts
                factores.append(f"✅ Visitante: últ.10 {aw}-{al} vs {hw}-{hl} +{pts}pt")
        else:
            factores.append(f"🟰 Últ.10 similar ({hw}-{hl} vs {aw}-{al})")
    else:
        factores.append("❓ Últ.10: sin datos")

    # ── Factor 8: Últimos 10 local/visita (1 pt) ──
    hw10, hl10 = _parse_rec(rec_h.get("home10", "—"))
    aw10, al10 = _parse_rec(rec_a.get("away10", "—"))
    if hw10 is not None and aw10 is not None:
        if hw10 >= aw10 + 2:
            pts_home += 0.3
            factores.append(f"✅ Local: local10 {hw10}-{hl10} vs visita10 {aw10}-{al10} +0.3pt")
        elif aw10 >= hw10 + 2:
            pts_away += 0.3
            factores.append(f"✅ Visitante: visita10 {aw10}-{al10} vs local10 {hw10}-{hl10} +0.3pt")
        else:
            factores.append(f"🟰 Local/visita últ.10 similar")
    else:
        factores.append("❓ Local/visita últ.10: sin datos")

    # ── Factor 9: Récord vs mano pitcher (1 pt) ──
    rvh_away = records.get(f"{away}_vs_{h_hand}", "—")  # visitante vs mano del local
    rvh_home = records.get(f"{home}_vs_{a_hand}", "—")  # local vs mano del visitante
    va_w, va_l = _parse_rec(rvh_away)
    vh_w, vh_l = _parse_rec(rvh_home)
    if va_w is not None and vh_w is not None and (va_w + va_l) > 0 and (vh_w + vh_l) > 0:
        va_pct = va_w / (va_w + va_l)
        vh_pct = vh_w / (vh_w + vh_l)
        diff9  = abs(va_pct - vh_pct)
        if diff9 >= 0.10:
            if va_pct > vh_pct:
                pts_away += 0.3
                factores.append(f"✅ Visitante: vs mano {h_hand} {rvh_away} vs {rvh_home} +0.3pt")
            else:
                pts_home += 0.3
                factores.append(f"✅ Local: vs mano {a_hand} {rvh_home} vs {rvh_away} +0.3pt")
        else:
            factores.append(f"🟰 Récord vs mano similar ({rvh_away} vs {rvh_home})")
    else:
        factores.append("❓ Récord vs mano pitcher: sin datos")

    # ── Factor 10: H2H temporada (0.5 pts) ──
    h2h_parts = _parse_rec(h2h) if h2h != "—" else (None, None)
    h2h_w, h2h_l = h2h_parts
    if h2h_w is not None and (h2h_w + h2h_l) > 0:
        if h2h_w > h2h_l:
            pts_home += 0.2
            factores.append(f"✅ Local: H2H {h2h} +0.2pt")
        elif h2h_l > h2h_w:
            pts_away += 0.2
            factores.append(f"✅ Visitante: H2H {h2h_l}-{h2h_w} a su favor +0.2pt")
        else:
            factores.append(f"🟰 H2H empatado {h2h}")
    else:
        factores.append("❓ H2H: sin datos (primera serie)")

    # ── Factor 11: Día de la semana (0.2 pts) ──
    game_dt_str = partido.get("game_date_utc", "")
    wday = None
    if game_dt_str:
        try:
            wday = datetime.fromisoformat(game_dt_str.replace("Z", "+00:00")).weekday()
        except Exception:
            pass
    WDAY_NAMES = {0:"Lun",1:"Mar",2:"Mié",3:"Jue",4:"Vie",5:"Sáb",6:"Dom"}
    if wday is not None:
        wd_h = rec_h.get("weekday", {}).get(wday, "—")
        wd_a = rec_a.get("weekday", {}).get(wday, "—")
        wd_hw, wd_hl = _parse_rec(wd_h)
        wd_aw, wd_al = _parse_rec(wd_a)
        if wd_hw is not None and wd_aw is not None and (wd_hw+wd_hl) > 0 and (wd_aw+wd_al) > 0:
            wd_h_pct = wd_hw / (wd_hw + wd_hl)
            wd_a_pct = wd_aw / (wd_aw + wd_al)
            if wd_h_pct > wd_a_pct + 0.15:
                pts_home += 0.1
                factores.append(f"✅ Local: {WDAY_NAMES[wday]} {wd_h} vs {wd_a} +0.1pt")
            elif wd_a_pct > wd_h_pct + 0.15:
                pts_away += 0.1
                factores.append(f"✅ Visitante: {WDAY_NAMES[wday]} {wd_a} vs {wd_h} +0.1pt")
            else:
                factores.append(f"🟰 Día {WDAY_NAMES.get(wday,'?')}: similar ({wd_h} vs {wd_a})")
        else:
            factores.append(f"❓ Récord día {WDAY_NAMES.get(wday,'?')}: sin datos")
    else:
        factores.append("❓ Día de la semana: no determinado")

    # ── Factor 12: Clima/Viento (0.2 pts) ──
    if clima is not None:
        wind_rel = clima.get("wind_rel", "")
        wind_kph  = clima.get("wind_kph", 0)
        precip    = clima.get("precip_prob", 0)
        wind_emoji = clima.get("wind_emoji", "")
        if wind_kph >= 20 and "Saliendo" in wind_rel:
            # Viento saliendo favorece bateadores → va al equipo que batea mejor últimamente
            _woba_h_gen = (batting_vs_R_14.get(home) or batting_vs_L_30.get(home) or {}).get("wOBA", 0)
            _woba_a_gen = (batting_vs_R_14.get(away) or batting_vs_L_30.get(away) or {}).get("wOBA", 0)
            if _woba_h_gen >= _woba_a_gen:
                pts_home += 0.2
                factores.append(f"✅ Local: viento saliendo {wind_kph:.0f}km/h + mejor bat reciente (wOBA {_woba_h_gen:.3f}) +0.2pt")
            else:
                pts_away += 0.2
                factores.append(f"✅ Visitante: viento saliendo {wind_kph:.0f}km/h + mejor bat reciente (wOBA {_woba_a_gen:.3f}) +0.2pt")
        elif wind_kph >= 20 and "Entrando" in wind_rel:
            factores.append(f"🌬️ Viento entrando {wind_kph:.0f}km/h — favorece pitchers, sin puntos asignados")
        elif precip >= 50:
            factores.append(f"🌧️ Lluvia probable {precip}% — posible suspensión o juego pesado")
        else:
            factores.append(f"🟰 Clima neutro ({wind_kph:.0f}km/h, lluvia {precip}%)")
    else:
        factores.append("🏟️ Estadio techado o sin datos de clima")

    # ── Factor 13: Campo local (dinámico según récords) ──
    rec_home = records.get(home, {})
    rec_away = records.get(away, {})
    def _rec_pct(s: str) -> float | None:
        try:
            w, l = s.split("-"); w, l = int(w), int(l)
            return w / (w + l) if (w + l) > 0 else None
        except Exception:
            return None
    home_home_pct = _rec_pct(rec_home.get("home10", "—"))
    away_away_pct = _rec_pct(rec_away.get("away10", "—"))
    if home_home_pct is not None and away_away_pct is not None:
        if home_home_pct > 0.5 and away_away_pct < 0.5:
            pts_home += 0.5
            factores.append(f"✅ Local: campo ({home_home_pct:.0%} casa) + visita débil fuera ({away_away_pct:.0%}) +0.5pt")
        elif home_home_pct > 0.5 and away_away_pct >= 0.5:
            pts_home += 0.2
            factores.append(f"🟡 Local: ambos positivos casa/visita — ventaja campo +0.2pt")
        elif home_home_pct <= 0.5 and away_away_pct > 0.5:
            pts_away += 0.2
            factores.append(f"✅ Visitante: local débil en casa ({home_home_pct:.0%}) + visita fuerte fuera ({away_away_pct:.0%}) +0.2pt")
        else:
            factores.append(f"🟰 Campo: ambos débiles casa/visita — sin puntos")
    else:
        # Sin datos suficientes: ventaja mínima fija al local
        pts_home += 0.2
        factores.append("🏠 Local: ventaja de campo por defecto +0.2pt")

    # ── Factor 14: Bateo con RISP ──
    risp_h = batting_risp.get(home, {})
    risp_a = batting_risp.get(away, {})
    rk_h   = risp_rank.get(home)
    rk_a   = risp_rank.get(away)
    def _risp_pts(rk):
        if rk is None:         return 0.0
        if rk <= 8:            return 0.6
        if rk <= 15:           return 0.35
        if rk <= 25:           return 0.0
        return -0.35
    def _risp_label(rk, n):
        if rk is None: return "sin datos"
        return f"#{rk}/{n} ({'Top 8' if rk<=8 else ('Top 15' if rk<=15 else ('Medio' if rk<=25 else 'Bottom 5'))})"
    n_risp = max(len(risp_rank), 1)
    if risp_h or risp_a:
        ph = _risp_pts(rk_h); pa = _risp_pts(rk_a)
        pts_home += ph; pts_away += pa
        lh = _risp_label(rk_h, n_risp); la = _risp_label(rk_a, n_risp)
        woba_h = risp_h.get("wOBA", "—") if risp_h else "—"
        woba_a = risp_a.get("wOBA", "—") if risp_a else "—"
        if ph > 0:
            factores.append(f"🔥 Local: RISP liga {lh}, wOBA {woba_h} {'+' if ph>=0 else ''}{ph}pt")
        elif ph < 0:
            factores.append(f"🔴 Local: RISP liga {lh}, wOBA {woba_h} {ph}pt")
        else:
            factores.append(f"🟡 Local: RISP liga {lh}, wOBA {woba_h} (0pt)")
        if pa > 0:
            factores.append(f"🔥 Visitante: RISP liga {la}, wOBA {woba_a} {'+' if pa>=0 else ''}{pa}pt")
        elif pa < 0:
            factores.append(f"🔴 Visitante: RISP liga {la}, wOBA {woba_a} {pa}pt")
        else:
            factores.append(f"🟡 Visitante: RISP liga {la}, wOBA {woba_a} (0pt)")
    else:
        factores.append("❓ RISP: sin datos disponibles")

    # ── Factor 15: Récord del equipo con este pitcher abridor ──
    def _pitcher_rec_pts(rec_str, min_starts=3):
        """Escala por tramos de win%, requiere >= min_starts."""
        try:
            w, l = rec_str.split("-")
            w, l = int(w), int(l)
            if w + l < min_starts:
                return None, rec_str
            win_pct = w / (w + l)
            if   win_pct >= 0.800: pts =  1.3   # ≥.800
            elif win_pct >= 0.700: pts =  0.6   # .700–.799
            elif win_pct >= 0.600: pts =  0.45  # .600–.699
            elif win_pct >= 0.550: pts =  0.2   # .550–.599
            elif win_pct >= 0.450: pts =  0.0   # zona neutra .450–.549
            elif win_pct >= 0.400: pts = -0.2   # .400–.449
            elif win_pct >= 0.300: pts = -0.45  # .300–.399
            elif win_pct >= 0.200: pts = -0.6   # .200–.299
            else:                  pts = -1.0   # <.200
            return pts, f"{w}-{l} ({win_pct:.0%})"
        except Exception:
            return None, rec_str

    rec_h_pit = pitcher_rec.get(h_pid, "—")
    rec_a_pit = pitcher_rec.get(a_pid, "—")
    ph_pit, lh_pit = _pitcher_rec_pts(rec_h_pit)
    pa_pit, la_pit = _pitcher_rec_pts(rec_a_pit)

    if ph_pit is not None:
        pts_home += ph_pit
        _ic = "✅" if ph_pit > 0 else ("🔴" if ph_pit < 0 else "🟰")
        factores.append(f"{_ic} Local: récord equipo con {partido.get('home_pitcher','starter')} = {lh_pit} ({ph_pit:+.2f}pt)")
    else:
        _lbl = "sin suficientes starts" if rec_h_pit not in ("—", "") else "sin datos"
        factores.append(f"❓ Local: récord equipo con starter ({_lbl})")

    if pa_pit is not None:
        pts_away += pa_pit
        _ic = "✅" if pa_pit > 0 else ("🔴" if pa_pit < 0 else "🟰")
        factores.append(f"{_ic} Visitante: récord equipo con {partido.get('away_pitcher','starter')} = {la_pit} ({pa_pit:+.2f}pt)")
    else:
        _lbl = "sin suficientes starts" if rec_a_pit not in ("—", "") else "sin datos"
        factores.append(f"❓ Visitante: récord equipo con starter ({_lbl})")

    return {
        "home":      home,
        "away":      away,
        "pts_home":  round(pts_home, 1),
        "pts_away":  round(pts_away, 1),
        "factores":  factores,
        "home_name": TEAM_NAMES.get(home, home),
        "away_name": TEAM_NAMES.get(away, away),
    }


def tab_pronostico():
    """Tab 🔮 Pronóstico: muestra ventaja heurística por partido del día."""
    st.markdown("### 🔮 Pronóstico de Ventaja por Partido")
    st.caption(
        "Sistema heurístico de 14 factores. No es un modelo estadístico. "
        "Margen ≥ 2pt = ventaja significativa."
    )

    # ── Selección de fecha ────────────────────────────────────────────────────
    fecha_sel = st.date_input(
        "Selecciona fecha",
        value=date.today(),
        key="pronostico_fecha",
    )

    # ── API Key FanDuel — lee de secrets si está disponible ───────────────────
    _key_from_secrets = st.secrets.get("ODDS_API_KEY", "") if hasattr(st, "secrets") else ""
    with st.expander("⚙️ Configurar odds FanDuel (The Odds API)", expanded=not bool(_key_from_secrets)):
        if _key_from_secrets:
            st.caption("✅ API Key cargada desde secrets.")
            odds_api_key = _key_from_secrets
        else:
            odds_api_key = st.text_input(
                "API Key (the-odds-api.com — tier gratuito 500 req/mes)",
                type="password",
                key="odds_api_key",
                help="Regístrate gratis en the-odds-api.com para obtener tu key"
            )

    with st.spinner("Cargando momios FanDuel..."):
        momios_fd = cargar_momios_fanduel(odds_api_key) if odds_api_key else {}

    with st.spinner("Cargando partidos del día..."):
        partidos = cargar_partidos_mlb(fecha_sel)

    if not partidos:
        st.info("No hay partidos registrados para esa fecha.")
        return

    st.markdown(f"**{len(partidos)} partidos el {fecha_sel.strftime('%A %d %b %Y')}**")

    # ── Cargar gamelogs e iniciadores ────────────────────────────────────────
    all_pids = []
    for p in partidos:
        for k in ("home_pitcher_id", "away_pitcher_id"):
            pid = p.get(k)
            if pid and pid not in all_pids:
                all_pids.append(pid)

    gamelogs_p: dict    = {}
    resumenes_p: dict   = {}
    pitcher_hands_p: dict = {}
    with st.spinner("Cargando stats de iniciadores..."):
        for pid in all_pids:
            df = cargar_gamelog_pitcher(pid, n_starts=4)
            gamelogs_p[pid]      = df
            resumenes_p[pid]     = _resumen_gamelog(df) if not df.empty else {}
            pitcher_hands_p[pid] = _fetch_pitcher_hand(pid)

    # ── Ranks slate ──────────────────────────────────────────────────────────
    slate_items_p = []
    for p in partidos:
        for pk, nk in [("away_pitcher_id", "away_pitcher"),
                       ("home_pitcher_id", "home_pitcher")]:
            pid  = p.get(pk)
            name = p.get(nk, "Por confirmar")
            if pid and name != "Por confirmar" and resumenes_p.get(pid):
                slate_items_p.append({"pitcher_id": pid, "FIP": resumenes_p[pid]["FIP"]})
    slate_items_p.sort(key=lambda x: x["FIP"])
    rank_dia_p = {it["pitcher_id"]: i + 1 for i, it in enumerate(slate_items_p)}
    n_rank_p   = len(slate_items_p)

    # ── Statcast bateo ───────────────────────────────────────────────────────
    with st.spinner("Cargando Statcast para bateo..."):
        raw_30_p = cargar_statcast_global(dias=30)

    today_p = date.today()
    if not raw_30_p.empty and "game_date" in raw_30_p.columns:
        _c14 = today_p - timedelta(days=14)
        _c16 = today_p - timedelta(days=16)
        _c17 = today_p - timedelta(days=17)
        raw_14_p = raw_30_p[raw_30_p["game_date"] >= _c14].copy()
        raw_16_p = raw_30_p[raw_30_p["game_date"] >= _c16].copy()
        raw_17_p = raw_30_p[raw_30_p["game_date"] >= _c17].copy()
    else:
        raw_14_p = raw_16_p = raw_17_p = pd.DataFrame()

    bat_vs_R_14_p  = _batting_from_statcast(raw_14_p, p_throws="R")
    bat_vs_L_30_p  = _batting_from_statcast(raw_30_p, p_throws="L")
    bat_vs_bp_16_p = _batting_from_statcast(raw_16_p, min_inning=6)
    bat_risp_17_p  = _batting_risp_from_statcast(raw_17_p, min_pa=10)
    _risp_srt_p    = sorted(bat_risp_17_p.items(), key=lambda x: x[1]["wOBA"], reverse=True)
    risp_rank_p    = {t: i + 1 for i, (t, _) in enumerate(_risp_srt_p)}

    # ── Statcast bullpen ─────────────────────────────────────────────────────
    with st.spinner("Cargando Statcast bullpen..."):
        raw_bull_p = cargar_statcast_global(dias=14)

    _today_bull = date.today()
    ranking_fip_p: dict = {}
    for _t in MLB_TEAMS:
        _s = _bull_disp(raw_bull_p, _t, _today_bull)
        if _s["FIP"] is not None:
            ranking_fip_p[_t] = _s["FIP"]
    sorted_p  = sorted(ranking_fip_p, key=lambda t: ranking_fip_p[t])
    rank_gl_p = {t: i + 1 for i, t in enumerate(sorted_p)}

    # ── Records y clima ──────────────────────────────────────────────────────
    records_cache: dict = {}
    h2h_cache:     dict = {}
    clima_cache:   dict = {}
    pitcher_rec_cache: dict = {}   # {pitcher_id: 'W-L'}
    with st.spinner("Cargando récords y clima..."):
        for p in partidos:
            home = p["home_abbr"]; away = p["away_abbr"]
            h_tid = MLB_TEAM_IDS.get(home)
            a_tid = MLB_TEAM_IDS.get(away)
            h_pid = p.get("home_pitcher_id")
            a_pid = p.get("away_pitcher_id")
            h_hand = pitcher_hands_p.get(h_pid, "R")
            a_hand = pitcher_hands_p.get(a_pid, "R")

            if h_tid and home not in records_cache:
                records_cache[home] = cargar_records_equipo(h_tid)
            if a_tid and away not in records_cache:
                records_cache[away] = cargar_records_equipo(a_tid)

            # vs mano
            vh_key = f"{away}_vs_{h_hand}"
            va_key = f"{home}_vs_{a_hand}"
            if a_tid and vh_key not in records_cache:
                records_cache[vh_key] = cargar_record_vs_hand(a_tid, h_hand)
            if h_tid and va_key not in records_cache:
                records_cache[va_key] = cargar_record_vs_hand(h_tid, a_hand)

            # H2H
            h2h_key = f"{home}_{away}"
            if h_tid and a_tid and h2h_key not in h2h_cache:
                h2h_cache[h2h_key] = cargar_h2h(h_tid, a_tid)

            # Clima
            if home not in clima_cache:
                clima_cache[home] = cargar_clima_partido(home, p.get("game_date_utc", ""))

            # Récord del equipo con cada pitcher abridor
            if h_pid and h_tid and h_pid not in pitcher_rec_cache:
                pitcher_rec_cache[h_pid] = cargar_record_equipo_con_pitcher(h_pid, h_tid)
            if a_pid and a_tid and a_pid not in pitcher_rec_cache:
                pitcher_rec_cache[a_pid] = cargar_record_equipo_con_pitcher(a_pid, a_tid)

    # ── Calcular y mostrar pronóstico por partido ────────────────────────────
    resultados = []
    for p in partidos:
        home = p["home_abbr"]; away = p["away_abbr"]
        h_pid = p.get("home_pitcher_id")
        a_pid = p.get("away_pitcher_id")
        h_hand = pitcher_hands_p.get(h_pid, "R")
        a_hand = pitcher_hands_p.get(a_pid, "R")
        h2h_str = h2h_cache.get(f"{home}_{away}", "—")
        clima_p = clima_cache.get(home)

        resultado = calcular_ventaja_partido(
            partido        = p,
            resumenes      = resumenes_p,
            raw_global     = raw_bull_p,
            batting_vs_R_14= bat_vs_R_14_p,
            batting_vs_L_30= bat_vs_L_30_p,
            batting_vs_bp_14= bat_vs_bp_16_p,
            rank_global    = rank_gl_p,
            rank_dia_lookup= rank_dia_p,
            n_rank_dia     = n_rank_p,
            pitcher_hands  = pitcher_hands_p,
            records        = records_cache,
            h2h            = h2h_str,
            clima          = clima_p,
            batting_risp   = bat_risp_17_p,
            risp_rank      = risp_rank_p,
            pitcher_rec    = pitcher_rec_cache,
        )
        resultados.append((p, resultado))

    # ── Tabla resumen ─────────────────────────────────────────────────────────
    sum_rows = []
    for p, r in resultados:
        diff = r["pts_home"] - r["pts_away"]
        if diff > 1.0:
            ventaja = f"🏠 {r['home_name']}"
        elif diff < -1.0:
            ventaja = f"✈️ {r['away_name']}"
        else:
            ventaja = "⚖️ Parejo"
        _mom = _match_momio(momios_fd, r["home_name"], r["away_name"])
        _ml_h = _fmt_ml(_mom["home_ml"]) if _mom else "—"
        _ml_a = _fmt_ml(_mom["away_ml"]) if _mom else "—"
        _prob_h = _ml_to_prob(_mom["home_ml"]) if _mom else None
        _prob_a = _ml_to_prob(_mom["away_ml"]) if _mom else None
        # Normalizar (quitar vig)
        if _prob_h and _prob_a:
            _tot = _prob_h + _prob_a
            _prob_h_norm = _prob_h / _tot
            _prob_a_norm = _prob_a / _tot
        else:
            _prob_h_norm = _prob_a_norm = None
        # Prob modelo
        _tot_pts = r["pts_home"] + r["pts_away"]
        _mod_h = r["pts_home"] / _tot_pts if _tot_pts > 0 else 0.5
        _mod_a = r["pts_away"] / _tot_pts if _tot_pts > 0 else 0.5
        # Valor vs mercado
        if _prob_h_norm:
            _valor = "📈 Valor local" if _mod_h > _prob_h_norm + 0.05 else ("📉 Valor visita" if _mod_a > _prob_a_norm + 0.05 else "⚖️ En línea")
        else:
            _valor = "—"
        sum_rows.append({
            "Visitante":     r["away_name"],
            "ML Vis.":       _ml_a,
            "Pts Vis.":      r["pts_away"],
            "Local":         r["home_name"],
            "ML Loc.":       _ml_h,
            "Pts Loc.":      r["pts_home"],
            "Diferencia":    round(diff, 1),
            "Ventaja":       ventaja,
            "FD Valor":      _valor,
            "Hora":          p.get("hora", "—"),
        })

    st.dataframe(
        pd.DataFrame(sum_rows).sort_values("Hora"),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    # ── Detalle por partido ───────────────────────────────────────────────────
    for p, r in resultados:
        home = r["home"]; away = r["away"]
        h_starter = p.get("home_pitcher", "Por confirmar")
        a_starter = p.get("away_pitcher", "Por confirmar")
        h_hand = pitcher_hands_p.get(p.get("home_pitcher_id"), "R")
        a_hand = pitcher_hands_p.get(p.get("away_pitcher_id"), "R")

        diff = r["pts_home"] - r["pts_away"]
        if diff > 1.0:
            ventaja_str = f"🏠 **Ventaja LOCAL** ({r['home_name']}) por {diff:.1f}pt"
            color = "#d4edda"
        elif diff < -1.0:
            ventaja_str = f"✈️ **Ventaja VISITANTE** ({r['away_name']}) por {abs(diff):.1f}pt"
            color = "#fff3cd"
        else:
            ventaja_str = f"⚖️ **Partido Parejo** (diferencia {abs(diff):.1f}pt)"
            color = "#e2e3e5"

        hora_str = p.get("hora", "—")
        with st.expander(
            f"{TEAM_NAMES.get(away, away)} @ {TEAM_NAMES.get(home, home)} — {hora_str} | "
            f"Vis {r['pts_away']:.1f}pt | Loc {r['pts_home']:.1f}pt",
            expanded=False,
        ):
            st.markdown(
                f"<div style='background:{color};padding:10px;border-radius:8px;margin-bottom:10px;'>"
                f"{ventaja_str}</div>",
                unsafe_allow_html=True,
            )

            # Odds FanDuel
            _mom_e = _match_momio(momios_fd, r["home_name"], r["away_name"])
            if _mom_e:
                _mh = _fmt_ml(_mom_e["home_ml"]); _ma = _fmt_ml(_mom_e["away_ml"])
                _ph = _ml_to_prob(_mom_e["home_ml"]); _pa = _ml_to_prob(_mom_e["away_ml"])
                _tot_p = _ph + _pa
                _ph_n = _ph / _tot_p; _pa_n = _pa / _tot_p
                _tot_pts_e = r["pts_home"] + r["pts_away"]
                _mh_pct = r["pts_home"] / _tot_pts_e if _tot_pts_e > 0 else 0.5
                _ma_pct = r["pts_away"] / _tot_pts_e if _tot_pts_e > 0 else 0.5
                _v_h = _mh_pct - _ph_n; _v_a = _ma_pct - _pa_n
                st.markdown(
                    f"<div style='background:#1a1a2e;color:#eee;padding:10px 16px;border-radius:8px;"
                    f"margin-bottom:10px;font-family:monospace;'>"
                    f"<b>🎰 FanDuel ML</b> &nbsp;|&nbsp; "
                    f"✈️ {r['away_name']}: <b>{_ma}</b> ({_pa_n*100:.0f}%) &nbsp;|&nbsp; "
                    f"🏠 {r['home_name']}: <b>{_mh}</b> ({_ph_n*100:.0f}%) &nbsp;|&nbsp; "
                    f"Modelo: ✈️{_ma_pct*100:.0f}% vs 🏠{_mh_pct*100:.0f}% &nbsp;|&nbsp; "
                    f"Valor: {'📈 LOCAL +'+str(round(_v_h*100))+'%' if _v_h > 0.05 else ('📈 VISITA +'+str(round(_v_a*100))+'%' if _v_a > 0.05 else '⚖️ En línea')}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.caption("🎰 FanDuel: sin datos de momios")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**✈️ Visitante:** {r['away_name']}")
                st.markdown(f"Starter: {a_starter} ({'Zurdo' if a_hand=='L' else 'Derecho'})")
                fip_a = resumenes_p.get(p.get("away_pitcher_id"), {}).get("FIP")
                if fip_a:
                    st.markdown(f"FIP: **{fip_a:.2f}**")
            with col2:
                st.markdown(f"**🏠 Local:** {r['home_name']}")
                st.markdown(f"Starter: {h_starter} ({'Zurdo' if h_hand=='L' else 'Derecho'})")
                fip_h = resumenes_p.get(p.get("home_pitcher_id"), {}).get("FIP")
                if fip_h:
                    st.markdown(f"FIP: **{fip_h:.2f}**")

            st.markdown("---")
            st.markdown("**Desglose de factores:**")
            for factor in r["factores"]:
                st.markdown(f"- {factor}")

            # Barra visual de puntaje
            total = r["pts_home"] + r["pts_away"]
            if total > 0:
                pct_home = r["pts_home"] / total
                pct_away = r["pts_away"] / total
                st.markdown(
                    f"<div style='display:flex;height:20px;border-radius:6px;overflow:hidden;margin-top:10px;'>"
                    f"<div style='width:{pct_away*100:.0f}%;background:#ffc107;'></div>"
                    f"<div style='width:{pct_home*100:.0f}%;background:#28a745;'></div>"
                    f"</div>"
                    f"<div style='display:flex;justify-content:space-between;font-size:0.8rem;'>"
                    f"<span>Visitante {r['pts_away']:.1f}pt</span>"
                    f"<span>Local {r['pts_home']:.1f}pt</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )




# =============================================================================
# TAB 5: BULLPEN USAGE — TODOS LOS EQUIPOS
# =============================================================================

def tab_bullpen_usage():  # noqa: C901
    st.markdown("## Bullpen Usage — Todos los Equipos")
    st.caption(
        "Stats últimos **17 días** (Statcast) · SV/HLD: temporada completa · "
        "Uso D-1…D-5: pitcheos por día (verde ≤15 · amarillo ≤30 · rojo >30)"
    )

    col_btn, col_info = st.columns([1, 4])
    with col_btn:
        st.button("Actualizar datos", type="primary", key="bu_refresh")

    today  = date.today()
    dias_5 = [(today - timedelta(days=i)) for i in range(1, 6)]
    day_cols   = [f"D-{i}" for i in range(1, 6)]
    day_labels = {f"D-{i}": (today - timedelta(days=i)).strftime("%m/%d") for i in range(1, 6)}

    # ── Cargar datos ──────────────────────────────────────────────────────────
    with st.spinner("Descargando Statcast (17 días, todos los equipos)..."):
        raw_global = cargar_statcast_global(dias=17)

    with st.spinner("Cargando Saves y Holds de la temporada..."):
        df_svhld = get_saves_holds_season()

    if raw_global.empty:
        st.error("No se pudo cargar Statcast. Verifica conexión.")
        return

    # ── Construir datos por pitcher de todos los equipos ──────────────────────
    team_data: dict[str, pd.DataFrame] = {}
    progress = st.progress(0, text="Procesando equipos...")

    for i, team in enumerate(MLB_TEAMS):
        progress.progress((i + 1) / len(MLB_TEAMS), text=f"Procesando {team}...")
        df_t = _extraer_apariciones_equipo(raw_global, team)
        if df_t.empty:
            team_data[team] = pd.DataFrame()
            continue

        svhld_team = (
            df_svhld[df_svhld["team"] == team]
            if not df_svhld.empty and "team" in df_svhld.columns
            else pd.DataFrame()
        )

        rows = []
        for pid, grp in df_t.groupby("pitcher_id"):
            name  = grp["pitcher_name"].iloc[0]
            tp    = int(grp["PA"].sum())
            ti    = float(grp["IP"].sum())
            tk    = int(grp["K"].sum())
            tb    = int(grp["BB"].sum())
            th    = int(grp["H"].sum())
            thr   = int(grp["HR"].sum())
            ter   = int(grp["ER"].sum())
            tw    = float(grp["woba_sum"].sum())
            g     = grp["game_pk"].nunique()
            pit17 = int(grp["pitches"].sum())

            uso_5d = {}
            for d in dias_5:
                dg = grp[grp["game_date"] == d]
                uso_5d[d] = int(dg["pitches"].sum()) if not dg.empty else 0

            sv = hld = svo = 0
            if not svhld_team.empty and "pitcher_id" in svhld_team.columns:
                p_row = svhld_team[svhld_team["pitcher_id"] == pid]
                if not p_row.empty:
                    sv  = int(p_row.iloc[0]["SV"])
                    hld = int(p_row.iloc[0]["HLD"])
                    svo = int(p_row.iloc[0]["SVO"])

            row = {
                "Pitcher": name,
                "G":       g,
                "IP":      round(ti, 1),
                "K%":      round(tk / tp * 100, 1) if tp > 0 else 0.0,
                "BB%":     round(tb / tp * 100, 1) if tp > 0 else 0.0,
                "ERA":     round(ter / ti * 9, 2)  if ti > 0 else 0.0,
                "FIP":     round(max(0.0, (13*thr + 3*tb - 2*tk) / ti + FIP_CONST), 2) if ti > 0 else 4.50,
                "WHIP":    round((th + tb) / ti, 2) if ti > 0 else 0.0,
                "wOBA":    round(tw / tp, 3)        if tp > 0 else 0.300,
                "SV":      sv,
                "HLD":     hld,
                "SVO":     svo,
                "SV+HLD":  sv + hld,
                "Pit17":   pit17,
            }
            for j, d in enumerate(dias_5):
                row[f"D-{j+1}"] = uso_5d[d]

            rows.append(row)

        if rows:
            df_team = pd.DataFrame(rows)
            # Ordenar: primero closers (SV desc), luego setup (HLD desc), luego por FIP
            df_team = df_team.sort_values(
                ["SV", "HLD", "FIP"], ascending=[False, False, True]
            ).reset_index(drop=True)
            team_data[team] = df_team
        else:
            team_data[team] = pd.DataFrame()

    progress.empty()

    # ── Helpers de estilo inline ──────────────────────────────────────────────
    def _fip_color(v):
        try:
            f = float(v)
            if f < 3.50:   return "color:#155724;font-weight:600"
            elif f < 4.50: return "color:#856404"
            else:           return "color:#721c24;font-weight:600"
        except:
            return ""

    def _uso_cell(v):
        try:
            n = int(v)
            if n == 0:    return "—", ""
            elif n <= 15: return str(n), "background:#d4edda"
            elif n <= 30: return str(n), "background:#fff3cd"
            else:          return str(n), "background:#f8d7da"
        except:
            return str(v), ""

    def _render_team_card(team: str, df: pd.DataFrame):
        nombre = TEAM_NAMES.get(team, team)
        sv_tot  = int(df["SV"].sum())
        hld_tot = int(df["HLD"].sum())
        pit5_tot = int(df[day_cols].values.sum())

        # Cabecera de la tarjeta
        st.markdown(
            f"<div style='background:#0d2137;color:white;padding:6px 10px;"
            f"border-radius:6px 6px 0 0;font-weight:700;font-size:0.95rem;'>"
            f"⚾ {team} — {nombre}"
            f"<span style='float:right;font-size:0.8rem;font-weight:400;'>"
            f"SV {sv_tot} · HLD {hld_tot} · Pit5d {pit5_tot}</span></div>",
            unsafe_allow_html=True,
        )

        if df.empty:
            st.markdown(
                "<div style='background:#f8f9fa;padding:8px 10px;"
                "border:1px solid #dee2e6;border-top:none;border-radius:0 0 6px 6px;"
                "color:#6c757d;font-size:0.8rem;'>Sin datos</div>",
                unsafe_allow_html=True,
            )
            return

        # Cabecera de columnas
        hdrs = ["Pitcher", "G", "IP", "K%", "BB%", "ERA", "FIP", "WHIP", "wOBA",
                "SV", "HLD"] + [day_labels[d] for d in day_cols]
        hdr_html = "".join(
            f"<th style='padding:3px 6px;font-size:0.72rem;white-space:nowrap;"
            f"border-bottom:2px solid #0d2137;text-align:center;'>{h}</th>"
            for h in hdrs
        )

        rows_html = ""
        for idx, r in df.iterrows():
            # Etiqueta de rol
            if r["SV"] > 0:
                role_badge = (
                    "<span style='background:#0d2137;color:white;border-radius:3px;"
                    "padding:1px 4px;font-size:0.65rem;margin-right:4px;'>SV</span>"
                )
            elif r["HLD"] > 0:
                role_badge = (
                    "<span style='background:#5a7a94;color:white;border-radius:3px;"
                    "padding:1px 4px;font-size:0.65rem;margin-right:4px;'>HLD</span>"
                )
            else:
                role_badge = ""

            fip_style = _fip_color(r["FIP"])
            bg_row = "#ffffff" if idx % 2 == 0 else "#f8f9fa"

            uso_cells = ""
            for d in day_cols:
                txt, bg = _uso_cell(r[d])
                uso_cells += (
                    f"<td style='text-align:center;padding:3px 6px;"
                    f"font-size:0.75rem;{bg}'>{txt}</td>"
                )

            rows_html += (
                f"<tr style='background:{bg_row};'>"
                f"<td style='padding:3px 8px;font-size:0.78rem;white-space:nowrap;'>"
                f"{role_badge}{r['Pitcher']}</td>"
                f"<td style='text-align:center;padding:3px 6px;font-size:0.75rem;'>{r['G']}</td>"
                f"<td style='text-align:center;padding:3px 6px;font-size:0.75rem;'>{r['IP']:.1f}</td>"
                f"<td style='text-align:center;padding:3px 6px;font-size:0.75rem;'>{r['K%']:.1f}</td>"
                f"<td style='text-align:center;padding:3px 6px;font-size:0.75rem;'>{r['BB%']:.1f}</td>"
                f"<td style='text-align:center;padding:3px 6px;font-size:0.75rem;'>{r['ERA']:.2f}</td>"
                f"<td style='text-align:center;padding:3px 6px;font-size:0.75rem;{fip_style}'>{r['FIP']:.2f}</td>"
                f"<td style='text-align:center;padding:3px 6px;font-size:0.75rem;'>{r['WHIP']:.2f}</td>"
                f"<td style='text-align:center;padding:3px 6px;font-size:0.75rem;'>{r['wOBA']:.3f}</td>"
                f"<td style='text-align:center;padding:3px 6px;font-size:0.75rem;font-weight:600;'>{r['SV']}</td>"
                f"<td style='text-align:center;padding:3px 6px;font-size:0.75rem;font-weight:600;'>{r['HLD']}</td>"
                f"{uso_cells}"
                f"</tr>"
            )

        table_html = (
            f"<div style='overflow-x:auto;border:1px solid #dee2e6;"
            f"border-top:none;border-radius:0 0 6px 6px;margin-bottom:18px;'>"
            f"<table style='border-collapse:collapse;width:100%;'>"
            f"<thead><tr style='background:#f0f2f5;'>{hdr_html}</tr></thead>"
            f"<tbody>{rows_html}</tbody>"
            f"</table></div>"
        )
        st.markdown(table_html, unsafe_allow_html=True)

    # ── Render: 2 equipos por fila ────────────────────────────────────────────
    teams_list = MLB_TEAMS[:]
    for i in range(0, len(teams_list), 2):
        c1, c2 = st.columns(2)
        with c1:
            t = teams_list[i]
            _render_team_card(t, team_data.get(t, pd.DataFrame()))
        with c2:
            if i + 1 < len(teams_list):
                t = teams_list[i + 1]
                _render_team_card(t, team_data.get(t, pd.DataFrame()))


# =============================================================================
# MAIN
# =============================================================================

def main():
    st.set_page_config(
        page_title="MLB Pronóstico Analyzer",
        page_icon="⚾",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.markdown("""
    <style>
    .stApp { background-color: #f0f2f5; }
    [data-testid="stSidebar"] { background-color: #e8eaed; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(
        "<h1 style='color:#0d2137;font-size:2rem;font-weight:800;'>⚾ MLB Pronóstico Analyzer</h1>"
        "<p style='color:#5a7a94;'>Bullpen · Partidos del Día · Pronóstico de Ventaja</p>",
        unsafe_allow_html=True,
    )

    if not HAS_PYBASEBALL:
        st.error("pybaseball no instalado. Ejecuta: pip install pybaseball")
        st.stop()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["🔥 Bullpen Equipo", "🗺️ Bullpen Liga", "📅 Partidos del Día", "🔮 Pronóstico", "📊 Bullpen Usage"]
    )

    with tab1:
        tab_bullpen_individual()

    with tab2:
        tab_bullpen_liga()

    with tab3:
        tab_partidos_dia()

    with tab4:
        tab_pronostico()

    with tab5:
        tab_bullpen_usage()


if __name__ == "__main__":
    main()
