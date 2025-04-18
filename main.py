import pandas as pd
import pydeck as pdk
import streamlit as st
import json
import re
import math
from io import BytesIO

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
elevation_scale = 0.0075
ordu_layer_data = []

for i, col in enumerate(year_columns):
    yil = int(col[:4])
    toplam_nufus = df[col].sum()
    ordu_layer_data.append({
        "YIL": yil,
        "NÜFUS": toplam_nufus,
        "lat": center_lat,
        "lon": center_lon + i * offset_step,
        "z": toplam_nufus * elevation_scale + 100  # yazı yüksekliği
    })

ordu_df = pd.DataFrame(ordu_layer_data)

# Kolonlar
ordu_layer = pdk.Layer(
    "ColumnLayer",
    data=ordu_df,
    get_position='[lon, lat]',
    get_elevation="NÜFUS",
    elevation_scale=elevation_scale,
    radius=350,
    get_fill_color="[255 - NÜFUS / 100, 100, NÜFUS / 100, 180]",
    pickable=True,
    auto_highlight=True,
    extruded=True,
)

# Tepedeki nüfus etiketleri
label_layer = pdk.Layer(
    "TextLayer",
    data=ordu_df,
    get_position='[lon, lat, z]',
    get_text="NÜFUS",
    get_size=18,
    get_color=[255, 0, 0],
    get_angle=0,
    get_alignment_baseline="'center'",
    get_text_anchor="'middle'"
)

# Harita çizimi
st.pydeck_chart(pdk.Deck(
    map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
    initial_view_state=pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=8,
        pitch=40,
    ),
    layers=[ordu_layer, label_layer],
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
        get_line_color=[255, 255, 255, 180],
        line_width_min_pixels=1,
    )

    st.pydeck_chart(pdk.Deck(
        map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
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

secili_yil_mahalle = st.selectbox(
    "Mahalle Haritası için Yıl Seçiniz",
    dropdown_years,
    key="mahalle_yil"
)

if secili_yil_mahalle:
    df["NÜFUS"] = df[f"{secili_yil_mahalle} YILI NÜFUSU"]

    # Session state init
    st.session_state.setdefault("filter_active", False)
    st.session_state.setdefault("pop_min", None)
    st.session_state.setdefault("pop_max", None)
    st.session_state.setdefault("range_input", "")

    # Sabit aralıklar tanımı
    min_pop, max_pop = int(df["NÜFUS"].min()), int(df["NÜFUS"].max())
    sabit_araliklar = {
        f"{min_pop}-{500}": (min_pop, 500),
        "500-1000": (500, 1000),
        "1000-2000": (1000, 2000),
        "2000-5000": (2000, 5000),
        f"5000-{max_pop}": (5000, max_pop)
    }

    def _format_and_store():
        txt = st.session_state.range_input.strip()
        parts = re.split(r"\s*[-–—]\s*", txt)
        fmt = []
        for p in parts:
            nums = re.sub(r"\D", "", p)
            if nums:
                fmt.append(f"{int(nums):,}".replace(",", "."))
        if len(fmt) == 2:
            st.session_state.range_input = f"{fmt[0]}-{fmt[1]}"

    # --- UI Düzenlemesi ---
    st.text_input(
        "Nüfus Aralığı Seç (örn: 500-1000 veya 5.000-10.000)",
        key="range_input",
        placeholder="5.000-10.000 formatında",
        on_change=_format_and_store
    )

    col_btn1, col_btn2, _ = st.columns([1, 1, 8])
    with col_btn1:
        gir = st.button("Gir", use_container_width=True, type="primary")
    with col_btn2:
        temizle = st.button("Temizle", use_container_width=True, type="secondary")

    if temizle:
        st.session_state.pop_min = None
        st.session_state.pop_max = None
        st.session_state.filter_active = False
        st.session_state.range_input = ""

    if gir:
        raw = st.session_state.range_input.replace(" ", "")
        if raw in sabit_araliklar:
            lo, hi = sabit_araliklar[raw]
        else:
            parts = re.split(r"[-–—]", raw)
            try:
                nums = sorted(int(re.sub(r"\D", "", p)) for p in parts if p)
                if len(nums) == 2:
                    lo, hi = nums
                else:
                    raise ValueError
            except:
                st.error("Geçersiz format. Örnek: 5.000-10.000 veya 500-1000")
                st.stop()

        st.session_state.pop_min = lo
        st.session_state.pop_max = hi
        st.session_state.filter_active = True

    # Veri filtrelemesi
    if st.session_state.filter_active:
        lo, hi = st.session_state.pop_min, st.session_state.pop_max
        st.markdown(f"**Seçilen Aralık:** {lo:,} – {hi:,}".replace(",", "."))
        df_mahalle = df[df["NÜFUS"].between(lo, hi)].copy()
    else:
        df_mahalle = df.copy()

    df_mahalle = df_mahalle[df_mahalle["NÜFUS"].notna()]
    gmin, gmax = df["NÜFUS"].min(), df["NÜFUS"].max()

    df_mahalle["color"] = df_mahalle["NÜFUS"].apply(
        lambda v: [int((v - gmin) / (gmax - gmin) * 255), 50, int((1 - (v - gmin) / (gmax - gmin)) * 255), 180])

    # --- Harita ---
    st.pydeck_chart(pdk.Deck(
        map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
        initial_view_state=pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=8,
            pitch=40,
        ),
        layers=[
            pdk.Layer(
                "ColumnLayer", data=df_mahalle,
                get_position="[lon, lat]", get_elevation="NÜFUS",
                elevation_scale=0.3, radius=150,
                get_fill_color="color", pickable=True,
                auto_highlight=True, extruded=True,
            ),
            pdk.Layer(
                "GeoJsonLayer", mahalle_geojson,
                stroked=True, filled=False,
                get_line_color=[3, 32, 252, 180], line_width_min_pixels=1
            )
        ],
        tooltip={"text": "{MAHALLE}, {İLÇE}: {NÜFUS} kişi"}
    ))

    # --- Excel indirme butonları ---
    col_excel1, col_excel2, _ = st.columns([1, 1, 6])

    with col_excel1:
        output = BytesIO()
        df_mahalle_filtered = df_mahalle[["İLÇE", "MAHALLE", "NÜFUS"]].copy()
        df_mahalle_filtered["YIL"] = secili_yil_mahalle
        df_mahalle_filtered.to_excel(output, index=False, sheet_name="Ham Veri")
        st.download_button(
            "Ham Veriyi indir",
            data=output.getvalue(),
            file_name=f"mahalle_ham_veri_{secili_yil_mahalle}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="secondary"
        )

    with col_excel2:
        pivot_output = BytesIO()
        pivot_df = pd.pivot_table(
            df_mahalle_filtered,
            index="MAHALLE",
            columns="YIL",
            values="NÜFUS",
            aggfunc="sum"
        )
        pivot_df.loc["Genel Toplam"] = pivot_df.sum(numeric_only=True)
        pivot_df.to_excel(pivot_output, sheet_name="Pivot Tablo")
        st.download_button(
            "Pivot Tabloyu indir",
            data=pivot_output.getvalue(),
            file_name=f"mahalle_pivot_{secili_yil_mahalle}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary"
        )

