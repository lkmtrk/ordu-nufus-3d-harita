import pandas as pd
import pydeck as pdk
import streamlit as st
import json

# Sayfa ayarları
st.set_page_config(page_title="Ordu Nüfus Haritası", layout="wide")
st.markdown("## 📊 Ordu İli Nüfus Haritası (2007 - 2024)")

# Veri yükle
df = pd.read_excel("koordinatlı_nufus_verisi.xlsx")
df.rename(columns={"Latitude": "lat", "Longitude": "lon"}, inplace=True)

# GeoJSON dosyalarını yükle
with open("ILCELER.geojson", "r", encoding="utf-8") as f:
    ilce_geojson = json.load(f)

with open("MAHALLELER.geojson", "r", encoding="utf-8") as f:
    mahalle_geojson = json.load(f)

# Yıl sütunlarını al
year_columns = [col for col in df.columns if "YILI NÜFUSU" in col]
dropdown_years = [col.split()[0] for col in year_columns]

# -------------------------------
# 1. ORDU GENEL NÜFUSU
# -------------------------------
st.markdown("### 🏙️ Ordu Genel Nüfusu 3D Harita (2007 - 2024)")

center_lat = df["lat"].mean()
center_lon = df["lon"].mean()

offset_step = 0.01
ordu_layer_data = []

for i, col in enumerate(year_columns):
    yil = int(col[:4])
    toplam_nufus = df[col].sum()
    ordu_layer_data.append({
        "YIL": yil,
        "NÜFUS": toplam_nufus,
        "lat": center_lat,
        "lon": center_lon + i * offset_step
    })

ordu_df = pd.DataFrame(ordu_layer_data)

ordu_layer = pdk.Layer(
    "ColumnLayer",
    data=ordu_df,
    get_position='[lon, lat]',
    get_elevation="NÜFUS",
    elevation_scale=0.0075,
    radius=350,
    get_fill_color="[255 - NÜFUS / 100, 100, NÜFUS / 100, 180]",
    pickable=True,
    auto_highlight=True,
    extruded=True,
)


st.pydeck_chart(pdk.Deck(
    map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
    initial_view_state=pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=8,
        pitch=40,
    ),
    layers=[ordu_layer],
    tooltip={"text": "YIL: {YIL}\nNÜFUS: {NÜFUS}"}
))

# -------------------------------
# 2. İLÇE BAZLI NÜFUS
# -------------------------------
st.markdown("### 🗺️ İlçe Bazlı Nüfus (Yıl Seçiniz)")

secili_yil_ilce = st.selectbox("İlçe Haritası için Yıl Seçiniz", dropdown_years, key="ilce_yil")
if secili_yil_ilce:
    selected_column_ilce = f"{secili_yil_ilce} YILI NÜFUSU"
    ilce_df = df.groupby("İLÇE")[[selected_column_ilce, "lat", "lon"]].mean().reset_index()
    ilce_df["NÜFUS"] = df.groupby("İLÇE")[selected_column_ilce].sum().values

    layer_ilce = pdk.Layer(
        "ColumnLayer",
        data=ilce_df,
        get_position="[lon, lat]",
        get_elevation="NÜFUS",
        elevation_scale=0.3,
        radius=3000,
        get_fill_color="[255 - NÜFUS / 100, 30, NÜFUS / 100, 200]",
        pickable=True,
        auto_highlight=True,
        extruded=True,
    )

    ilce_border_layer = pdk.Layer(
        "GeoJsonLayer",
        ilce_geojson,
        stroked=True,
        filled=False,
        get_line_color=[255, 0, 255, 180],  # yeni renk: magenta
        line_width_min_pixels=1,
    )


    st.pydeck_chart(pdk.Deck(
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        initial_view_state=pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=8,
            pitch=40,
        ),
        layers=[layer_ilce, ilce_border_layer],
        tooltip={"text": "{İLÇE}: {NÜFUS} kişi"}
    ))

# -------------------------------
# 3. MAHALLE BAZLI NÜFUS
# -------------------------------
st.markdown("### 🏘️ Mahalle Bazlı Nüfus Haritası (Yıl Seçiniz)")

secili_yil_mahalle = st.selectbox("Mahalle Haritası için Yıl Seçiniz", dropdown_years, key="mahalle_yil")
if secili_yil_mahalle:
    selected_column_mahalle = f"{secili_yil_mahalle} YILI NÜFUSU"
    df["NÜFUS"] = df[selected_column_mahalle]

    layer_mahalle = pdk.Layer(
        "ColumnLayer",
        data=df,
        get_position="[lon, lat]",
        get_elevation="NÜFUS",
        elevation_scale=0.3,
        radius=150,
        get_fill_color="[255 - NÜFUS / 100, 50, NÜFUS / 100, 200]",
        pickable=True,
        auto_highlight=True,
        extruded=True,
    )

    mahalle_border_layer = pdk.Layer(
        "GeoJsonLayer",
        mahalle_geojson,
        stroked=True,
        filled=False,
        get_line_color=[3, 32, 252, 180],  # yeni renk: mavi
        line_width_min_pixels=1,
    )


    st.pydeck_chart(pdk.Deck(
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        initial_view_state=pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=8,
            pitch=40,
        ),
        layers=[layer_mahalle, mahalle_border_layer],
        tooltip={"text": "{MAHALLE}, {İLÇE}: {NÜFUS} kişi"}
    ))
