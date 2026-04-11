import io
import zipfile
import pandas as pd
import streamlit as st
from pathlib import Path
import shutil
from PIL import Image

st.set_page_config(page_title="Elvira Image Assigner", layout="wide")

# =====================================================
# OTTIMIZZAZIONE IMMAGINI
# =====================================================

def optimize_image(uploaded_file, max_size=1600, quality=75):
    img = Image.open(uploaded_file)

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    img.thumbnail((max_size, max_size))

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality, optimize=True)
    buffer.seek(0)

    return buffer


# =====================================================
# LOGIN
# =====================================================

def require_password():
    if st.session_state.get("auth_ok"):
        return True

    st.markdown("""
    <style>
      #MainMenu {visibility: hidden;}
      footer {visibility: hidden;}
      header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

    left, center, right = st.columns([1, 1.2, 1])

    with center:
        with st.container(border=True):
            try:
                st.image("elvira_logo.png", use_container_width=True)
            except:
                pass

            st.markdown("## Elvira Image Assigner")
            st.caption("Accesso riservato")

            pwd = st.text_input("Password", type="password")

            if st.button("Accedi", use_container_width=True):
                if pwd == st.secrets.get("APP_PASSWORD", ""):
                    st.session_state["auth_ok"] = True
                    st.rerun()
                else:
                    st.error("Password errata")

    return False


if not require_password():
    st.stop()


# =====================================================
# SETUP
# =====================================================

out_dir = Path("output_images")
out_dir.mkdir(exist_ok=True)

if "temp_images" not in st.session_state:
    st.session_state.temp_images = {}


def safe_str(x):
    if pd.isna(x):
        return ""
    s = str(x).strip()
    return "" if s.lower() == "nan" else s


def url_to_basename(x):
    if pd.isna(x):
        return ""
    s = str(x).strip()
    if not s:
        return ""
    s = s.split("?")[0]
    return s.rsplit("/", 1)[-1]


# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:
    st.subheader("Sessione")

    if st.button("🚪 Logout", use_container_width=True):
        st.session_state["auth_ok"] = False
        st.rerun()

    st.divider()

    st.subheader("Download immagini")

    files = [p for p in out_dir.glob("*") if p.is_file()]
    if files:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for p in files:
                z.write(p, arcname=p.name)
        buf.seek(0)

        st.download_button("⬇️ Scarica ZIP", buf, "output_images.zip")

    st.divider()

    if st.button("🗑️ Svuota output_images"):
        shutil.rmtree(out_dir, ignore_errors=True)
        out_dir.mkdir(exist_ok=True)
        st.session_state.temp_images = {}
        st.rerun()


# =====================================================
# APP
# =====================================================

st.title("Gestione immagini prodotti")

csv_file = st.file_uploader("Carica CSV", type=["csv"])
if not csv_file:
    st.stop()

df = pd.read_csv(csv_file)

image_cols = [c for c in df.columns if c.lower().startswith("image")]

color_col = "Colore" if "Colore" in df.columns else None
color_code_col = "color_code" if "color_code" in df.columns else None
brand_col = "Brand" if "Brand" in df.columns else None
season_col = "Stagione" if "Stagione" in df.columns else None
type_col = "Type" if "Type" in df.columns else None

rows = []
seen = set()

for _, row in df.iterrows():

    title = safe_str(row.get("Title", ""))
    color = safe_str(row.get(color_col, ""))
    color_code = safe_str(row.get(color_code_col, ""))
    brand = safe_str(row.get(brand_col, ""))
    season = safe_str(row.get(season_col, ""))
    ptype = safe_str(row.get(type_col, ""))

    for col in image_cols:
        b = url_to_basename(row.get(col, ""))
        if not b:
            continue

        key = (title, color, color_code, col, b)
        if key in seen:
            continue
        seen.add(key)

        rows.append({
            "Title": title,
            "Colore": color,
            "color_code": color_code,
            "Brand": brand,
            "Stagione": season,
            "Type": ptype,
            "image_col": col,
            "basename": b
        })

all_df = pd.DataFrame(rows)

# =====================================================
# FILTRI
# =====================================================

st.subheader("Filtri")

color_map = all_df[["Colore", "color_code"]].drop_duplicates().fillna("")

color_options = [
    f"{r['Colore']} ({r['color_code']})" if r["color_code"] else r["Colore"]
    for _, r in color_map.iterrows()
]

brands = sorted(all_df["Brand"].dropna().unique())
seasons = sorted(all_df["Stagione"].dropna().unique())
types = sorted(all_df["Type"].dropna().unique())

c1, c2, c3, c4 = st.columns(4)

with c1:
    selected_brands = st.multiselect("Brand", brands)
with c2:
    selected_seasons = st.multiselect("Stagione", seasons)
with c3:
    selected_types = st.multiselect("Type", types)
with c4:
    selected_color_labels = st.multiselect("Colore", color_options)

selected_colors = [c.split(" (")[0] for c in selected_color_labels]

filtered_df = all_df.copy()

if selected_brands:
    filtered_df = filtered_df[filtered_df["Brand"].isin(selected_brands)]
if selected_seasons:
    filtered_df = filtered_df[filtered_df["Stagione"].isin(selected_seasons)]
if selected_types:
    filtered_df = filtered_df[filtered_df["Type"].isin(selected_types)]
if selected_colors:
    filtered_df = filtered_df[filtered_df["Colore"].isin(selected_colors)]

titles = sorted(filtered_df["Title"].unique())
selected_title = st.selectbox("Prodotto", titles)

prod_df = filtered_df[filtered_df["Title"] == selected_title]

# =====================================================
# UI DAM
# =====================================================

for _, r in prod_df.iterrows():

    b = r["basename"]
    color = r["Colore"]
    code = r["color_code"]

    label = f"{color} ({code})" if code else color

    st.subheader(f"{r['image_col']} {label} • {b}")

    c1, c2, c3 = st.columns([1, 1, 0.5])

    img_path = out_dir / b

    # =========================
    # UPLOAD
    # =========================
    with c1:
        up = st.file_uploader("Carica immagine", key=f"up_{b}")

        if up:
            optimized = optimize_image(up)
            img_path.write_bytes(optimized.getvalue())

            st.session_state.temp_images[b] = optimized.getvalue()

            st.success("✅ Caricata")

    # =========================
    # PREVIEW
    # =========================
    with c2:

        if b in st.session_state.temp_images:
            st.image(st.session_state.temp_images[b])

        elif img_path.exists():
            try:
                st.image(img_path.read_bytes())
            except:
                st.warning("Errore immagine")

        else:
            st.info("Nessuna immagine")

    # =========================
    # DELETE
    # =========================
    with c3:
        if img_path.exists() or b in st.session_state.temp_images:

            if st.button("🗑️", key=f"del_{b}"):

                if img_path.exists():
                    try:
                        img_path.unlink()
                    except:
                        pass

                if b in st.session_state.temp_images:
                    del st.session_state.temp_images[b]

                st.success("Eliminata")
