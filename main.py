import pandas as pd
import pydeck as pdk
import streamlit as st
import json
import re
import math
import colorsys  # renk paleti için HSV dönüşümü
from io import BytesIO

# Kategori bazlı renk fonksiyonu
def kategori_renk(v):
    if v <= 5000:
        # 0-5000 aralığı kahverengi
        return [166, 86, 40, 180]
    elif v <= 10000:
        # 5000-10000 aralığı mor
        return [152, 78, 163, 180]
    elif v <= 15000:
        # 10000-15000 aralığı yeşil
        return [77, 175, 74, 180]
    elif v <= 20000:
        # 15000-20000 aralığı mavi
        return [55, 126, 184, 180]
    elif v <= 25000:
        # 20000-25000 aralığı turuncu
        return [255, 127, 0, 180]
    elif v <= 30000:
        # 25000-30000 aralığı sarı
        return [255, 255, 51, 180]
    else:
        # 30000+ aralığı kırmızı
        return [228, 26, 28, 180]
    
# İlçe kategori renk fonksiyonu ve manuel aralık atama (7 kategori)
def ilce_renk(v):
    if v <= 10000:
        # 0–10.000
        return [166, 86, 40, 180]
    elif v <= 13000:
        # 10.000–13.000
        return [152, 78, 163, 180]
    elif v <= 20000:
        # 13.000–20.000
        return [77, 175, 74, 180]
    elif v <= 25000:
        # 20.000–25.000
        return [55, 126, 184, 180]
    elif v <= 100000:
        # 25.000–100.000
        return [255, 127, 0, 180]
    elif v <= 200000:
        # 100.000–200.000
        return [255, 255, 51, 180]
    else:
        # 200.000–250.000
        return [228, 26, 28, 180]


# Sayfa ayarları
st.set_page_config(page_title="Ordu Nüfus Haritası", layout="wide")
# Global CSS ile PyDeck tooltip arka planı ve metin rengi özelleştirme
st.markdown("""
<style>
  .deck-tooltip {
    background-color: magenta !important;
    color: white !important;
    border-radius: 4px;
    padding: 4px;
  }
</style>
""", unsafe_allow_html=True)

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
center_lat, center_lon = df["lat"].mean(), df["lon"].mean()
offset_step = 0.01
elevation_scale = 0.0075
ordu_layer_data = []
n = len(year_columns)
for i, col in enumerate(year_columns):
    yil = int(col[:4])
    toplam_nufus = df[col].sum()
    # HSV ile eşit aralıklı tonlar
    hue = i / n
    r, g, b = colorsys.hsv_to_rgb(hue, 0.8, 0.9)
    renk = [int(r * 255), int(g * 255), int(b * 255), 180]
    ordu_layer_data.append({
        "YIL": yil,
        "NÜFUS": toplam_nufus,
        "lat": center_lat,
        "lon": center_lon + i * offset_step,
        "z": toplam_nufus * elevation_scale + 100,
        "color": renk
    })
ordu_df = pd.DataFrame(ordu_layer_data)
ordu_df['NÜFUS_FMT'] = ordu_df['NÜFUS'].apply(lambda v: f"{int(v):,}".replace(',', '.'))
ordu_layer = pdk.Layer(
    "ColumnLayer", data=ordu_df,
    get_position='[lon, lat]', get_elevation="NÜFUS",
    elevation_scale=elevation_scale, radius=350,
    get_fill_color="color", pickable=True,
    auto_highlight=True, extruded=True
)
label_layer = pdk.Layer(
    "TextLayer", data=ordu_df,
    get_position='[lon, lat, z]', get_text="NÜFUS",
    get_size=18, get_color=[0, 0, 0],
    get_alignment_baseline="'center'",
    get_text_anchor="'middle'"
)
st.pydeck_chart(pdk.Deck(
    map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
    initial_view_state=pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=8, pitch=40),
    layers=[ordu_layer, label_layer],
    tooltip={"text": "YIL: {YIL}\nNÜFUS: {NÜFUS_FMT}"}
))

# -------------------------------
# 2. İLÇE BAZLI NÜFUS Harita ve Filtre
# -------------------------------
st.markdown("### 🗺️ İlçe Bazlı Nüfus Haritası (Yıl & Nüfus Aralığı)")

secili_yil_ilce = st.selectbox(
    "İlçe Haritası için Yıl Seçiniz",
    dropdown_years,
    index=dropdown_years.index("2024"),  # 2024 varsayılan
    key="ilce_yil"
)
if secili_yil_ilce:
    # Veri hazırlama
    df_ilce = df.groupby("İLÇE")[f"{secili_yil_ilce} YILI NÜFUSU"].sum().reset_index()
    df_ilce.rename(columns={f"{secili_yil_ilce} YILI NÜFUSU": "NÜFUS"}, inplace=True)
    df_ilce["lat"] = df.groupby("İLÇE")["lat"].mean().values
    df_ilce["lon"] = df.groupby("İLÇE")["lon"].mean().values

    # Filtre UI
    st.session_state.setdefault("ilce_filter", False)
    st.session_state.setdefault("ilce_range", "")
    
    def fmt_ilce():
        txt = st.session_state.ilce_range
        parts = re.split(r"[-–—]", txt)
        if len(parts)==2:
            try:
                lo = int(parts[0].replace('.', ''))
                hi = int(parts[1].replace('.', ''))
                st.session_state.ilce_range = f"{lo}-{hi}"
            except:
                pass

    st.text_input(
        "Nüfus Aralığı Seç (örn: 500-1000)",
        key="ilce_range",
        placeholder="500-1000",
        on_change=fmt_ilce
    )
    c1, c2, _ = st.columns([1,1,8])
    with c1:
        ilce_gir = st.button("Gir", type="primary", key="ilce_gir", use_container_width=True)
    with c2:
        ilce_temizle = st.button("Temizle", type="secondary", key="ilce_temizle", use_container_width=True)

    if ilce_temizle:
        st.session_state.ilce_filter = False
        st.session_state.ilce_range = ""
    if ilce_gir:
        st.session_state.ilce_filter = True

    # Filtreleme
    if st.session_state.ilce_filter and st.session_state.ilce_range:
        lo, hi = map(int, st.session_state.ilce_range.split("-"))
        df_ilce = df_ilce[df_ilce["NÜFUS"].between(lo, hi)]
        st.markdown(f"**Seçilen İlçe Aralığı:** {lo} – {hi}")
        count = df_ilce.shape[0]
        st.info(f"Kriterlere uygun {count} ilçe bulundu")

    # İlçe nüfus formatlama (bin ayracı, ondalık kısmı yok)
    df_ilce['NÜFUS_FMT'] = df_ilce['NÜFUS'].apply(lambda v: f"{int(v):,}".replace(',', '.'))


    # Renk kategorileri (5)
    df_ilce["color"] = df_ilce["NÜFUS"].apply(ilce_renk)

    # Harita
    layer_ilce = pdk.Layer(
        "ColumnLayer", data=df_ilce,
        get_position="[lon, lat]", get_elevation="NÜFUS",
        elevation_scale=0.3, radius=3000,
        get_fill_color="color", pickable=True,
        auto_highlight=True, extruded=True
    )
    border_ilce = pdk.Layer(
        "GeoJsonLayer", ilce_geojson,
        stroked=True, filled=False,
        get_line_color=[255,0,255,200], line_width_min_pixels=1
    )
    st.pydeck_chart(pdk.Deck(
        map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
        initial_view_state=pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=8, pitch=40),
        layers=[layer_ilce, border_ilce],
        tooltip={"text":"{İLÇE}: {NÜFUS_FMT}"}
    ))

                # Excel indirme
    ea, eb, _ = st.columns([1,1,8])
    with ea:
        out_ilce = BytesIO()
        # Ham İlçe Verisi: yıl sütunu ekle
        df_ilce_export = df_ilce.copy()
        df_ilce_export["YIL"] = secili_yil_ilce
        df_ilce_export = df_ilce_export[["İLÇE", "YIL", "NÜFUS"]]
        df_ilce_export.to_excel(out_ilce, index=False, sheet_name="Ham İlçe Verisi")
        st.download_button(
            "Ham Veriyi indir",
            data=out_ilce.getvalue(),
            file_name=f"ilce_ham_{secili_yil_ilce}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="secondary"
        )
    with eb:
        outp_ilce = BytesIO()
        # Pivot İlçe: yıl sütunu ekle
        piv_ilce = df_ilce_export.groupby("İLÇE")["NÜFUS"].sum().reset_index()
        piv_ilce["YIL"] = secili_yil_ilce
        piv_ilce = piv_ilce[["İLÇE", "YIL", "NÜFUS"]]
        # Genel Toplam satırı ekle
        toplam = piv_ilce["NÜFUS"].sum()
        # pandas 2+ append yerine concat kullan
        toplam_df = pd.DataFrame([{"YIL": secili_yil_ilce, "İLÇE": "Genel Toplam", "NÜFUS": toplam}])
        piv_ilce = pd.concat([piv_ilce, toplam_df], ignore_index=True)
        piv_ilce.to_excel(outp_ilce, index=False, sheet_name="Pivot İlçe")
        st.download_button(
            "Pivot Tabloyu indir",
            data=outp_ilce.getvalue(),
            file_name=f"ilce_pivot_{secili_yil_ilce}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary"
        )


# -------------------------------
# 3. MAHALLE BAZLI NÜFUS
# -------------------------------

st.markdown("### 🏘️ Mahalle Bazlı Nüfus Haritası (Yıl & Nüfus Aralığı)")

secili_yil_mahalle = st.selectbox(
    "Mahalle Haritası için Yıl Seçiniz",
    dropdown_years,
    index=dropdown_years.index("2024"),  # 2024 varsayılan
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

         # Filtre sonucu sayısı
        count_ilce = df_mahalle["İLÇE"].nunique()
        count_mah  = df_mahalle.shape[0]
        st.info(f"Kriterlere uygun {count_ilce} ilçede {count_mah} mahalle bulundu")

    else:
        df_mahalle = df.copy()

    df_mahalle = df_mahalle[df_mahalle["NÜFUS"].notna()]
    df_mahalle['NÜFUS_FMT'] = df_mahalle['NÜFUS'].apply(lambda v: f"{int(v):,}".replace(',', '.'))
    gmin, gmax = df["NÜFUS"].min(), df["NÜFUS"].max()

    df_mahalle["color"] = df_mahalle["NÜFUS"].apply(kategori_renk)


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
        tooltip={"text": "{MAHALLE}, {İLÇE}: {NÜFUS_FMT}"}
    ))

    # --- Excel indirme butonları ---
    col_excel1, col_excel2, _ = st.columns([1, 1, 8])

    with col_excel1:
        output = BytesIO()
        # 1) Ham Veri: tüm kayıtları al
        df_mahalle_filtered = df_mahalle.copy()
        # 2) Yıl sütunu ekle
        df_mahalle_filtered["YIL"] = secili_yil_mahalle
        # 3) Saf URL sütunu ekle (lat/lon’dan)
        df_mahalle_filtered["KONUMA GİT"] = df_mahalle_filtered.apply(
            lambda row: f"https://www.google.com/maps?q={row['lat']},{row['lon']}&z=13&hl=tr",
            axis=1
        )
        # 4) Sadece gerekli sütunları seç
        df_export = df_mahalle_filtered[["İLÇE", "MAHALLE", "YIL", "NÜFUS", "KONUMA GİT"]]
        # 5) Gerçek Excel hyperlink hücreleri oluşturmak için xlsxwriter
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df_export.to_excel(writer, sheet_name="Ham Veri", index=False)
            workbook  = writer.book
            worksheet = writer.sheets["Ham Veri"]
            link_col = df_export.columns.get_loc("KONUMA GİT")
            for idx, url in enumerate(df_export["KONUMA GİT"], start=1):
                worksheet.write_url(idx, link_col, url, string="Git")

        # 6) İndirme butonunu oluştur
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

        # 1) “KONUMA GİT” sütununu hazırla
        df_mahalle_filtered = df_mahalle.copy()
        df_mahalle_filtered["YIL"] = secili_yil_mahalle
        df_mahalle_filtered["KONUMA GİT"] = df_mahalle_filtered.apply(
            lambda row: f"https://www.google.com/maps?q={row['lat']},{row['lon']}&z=13&hl=tr",
            axis=1
        )

        # 2) Pivot tabloyu İlçe + Mahalle bazında oluştur
        pivot_df = pd.pivot_table(
            df_mahalle_filtered,
            index=["İLÇE", "MAHALLE"],
            columns="YIL",
            values="NÜFUS",
            aggfunc="sum"
        ).reset_index()

        # 3) Genel Toplam satırını ekle
        totals = pivot_df.select_dtypes(include=[int, float]).sum()
        totals["İLÇE"] = "Genel Toplam"
        totals["MAHALLE"] = ""
        pivot_df = pd.concat([pivot_df, totals.to_frame().T], ignore_index=True)

        # 4) Son sütun olarak “KONUMA GİT” ekle (Genel Toplam için boş bırak)
        coord_map = df_mahalle_filtered.set_index(["İLÇE", "MAHALLE"])["KONUMA GİT"]
        pivot_df["KONUMA GİT"] = pivot_df.apply(
            lambda row: coord_map.get((row["İLÇE"], row["MAHALLE"]), ""),
            axis=1
        )

        # 5) Gerçek hyperlink hücrelerini yaz (xlsxwriter)
        with pd.ExcelWriter(pivot_output, engine="xlsxwriter") as writer:
            pivot_df.to_excel(writer, sheet_name="Pivot Tablo", index=False)
            workbook  = writer.book
            worksheet = writer.sheets["Pivot Tablo"]
            git_col = pivot_df.columns.get_loc("KONUMA GİT")
            for idx, url in enumerate(pivot_df["KONUMA GİT"], start=1):
                if url:
                    worksheet.write_url(idx, git_col, url, string="Git")

        # 6) Download butonu
        st.download_button(
            "Pivot Tabloyu indir",
            data=pivot_output.getvalue(),
            file_name=f"mahalle_pivot_{secili_yil_mahalle}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary"
        )
