"""Hărți folium cu pini în stilul SKILLIO."""
import folium
from streamlit_folium import st_folium
 
from core import config
 
from .comp import esc, initiale
 
# Harta de bază: OpenStreetMap (gratuită, fără cheie). CARTO cere acum cheie și afișa „KEY REQUIRED”.
# Poți pune alt furnizor în .env: MAP_TILES=... și MAP_ATTR=...
TILES = config._env("MAP_TILES", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
ATTR = config._env("MAP_ATTR", "© OpenStreetMap contributors")
 
 
def _pin(text, culoare, mare=False):
    s = 34 if mare else 30
    return folium.DivIcon(
        icon_size=(s, s + 8), icon_anchor=(s // 2, s + 6),
        html=(f'<div style="width:{s}px;height:{s}px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);'
              f'background:{culoare};border:2.5px solid #fff;box-shadow:0 3px 8px rgba(0,0,0,.35);display:grid;'
              f'place-items:center"><span style="transform:rotate(45deg);color:#fff;font:800 11px '
              f'Plus Jakarta Sans,sans-serif">{esc(text)}</span></div>'))
 
 
def _eu(lat, lon):
    return folium.CircleMarker((lat, lon), radius=8, color="#fff", weight=3, fill=True, fill_color="#2950b8",
                               fill_opacity=1, tooltip="Tu")
 
 
def harta(centru, zoom=13):
    return folium.Map(location=centru, zoom_start=zoom, tiles=TILES, attr=ATTR, control_scale=False,
                      zoom_control=False, prefer_canvas=True)
 
 
def arata(m, key, inaltime=300, click=False):
    ret = ["last_object_clicked_tooltip"] if click else []
    out = st_folium(m, key=key, height=inaltime, use_container_width=True, returned_objects=ret)
    if click and out:
        return out.get("last_object_clicked_tooltip")
    return None
 
 
def harta_mesteri(mesteri, lat, lon, key="hm", inaltime=300):
    """Meșterii din apropiere; click pe pin -> întoarce id-ul meșterului."""
    m = harta((lat, lon), 13)
    _eu(lat, lon).add_to(m)
    for x in mesteri:
        if x.get("raza_km"):
            folium.Circle((x["lat"], x["lon"]), radius=x["raza_km"] * 1000, color="#127a4e", weight=0,
                          fill=True, fill_opacity=0.03).add_to(m)
    for x in mesteri:
        cul = "#127a4e" if x["disponibil"] else "#8a9a92"
        folium.Marker((x["lat"], x["lon"]), icon=_pin(initiale(x["nume"]), cul),
                      tooltip=f'#{x["id"]} {x["nume"]} · Trust {x["trust"]["scor"]}').add_to(m)
    t = arata(m, key, inaltime, click=True)
    if t and t.startswith("#"):
        try:
            return int(t[1:].split()[0])
        except ValueError:
            return None
    return None
 
 
def harta_lucrari(lucrari, lat, lon, key="hl", inaltime=280):
    """Solicitările pentru meșter; urgentele sunt portocalii. Click -> id lucrare."""
    m = harta((lat, lon), 13)
    _eu(lat, lon).add_to(m)
    for l in lucrari:
        cul = "#ea580c" if l["urgent"] else "#127a4e"
        folium.Marker((l["lat"], l["lon"]), icon=_pin("!" if l["urgent"] else config.MESERII[l["meserie"]]
                                                       ["nume"][0], cul, l["urgent"]),
                      tooltip=f'#{l["id"]} {l["titlu"]}').add_to(m)
    t = arata(m, key, inaltime, click=True)
    if t and t.startswith("#"):
        try:
            return int(t[1:].split()[0])
        except ValueError:
            return None
    return None
 
 
def harta_traseu(a, b, key, inaltime=200):
    """Meșter (a) și adresa clientului (b)."""
    m = harta(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), 13)
    folium.PolyLine([a, b], color="#2950b8", weight=4, dash_array="8 8").add_to(m)
    folium.Marker(a, icon=_pin("M", "#127a4e")).add_to(m)
    folium.Marker(b, icon=_pin("C", "#0f2a20", True)).add_to(m)
    m.fit_bounds([a, b], padding=(30, 30))
    arata(m, key, inaltime)
 