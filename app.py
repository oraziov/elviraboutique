import io
import zipfile
import pandas as pd
import streamlit as st
from pathlib import Path
import shutil

st.set_page_config(page_title="Elvira Image Assigner", layout="wide")

# =====================================================
# LOGIN
# =====================================================

def require_password():
    if st.session_state.get("auth_ok"):
        return True

    left, center, right = st.columns([1, 1.2, 1])

    with center:
        with st.container(border=True):
            st.image("elvira_logo.png", use_container_width=True)
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

def safe_str(x):
    if pd.isna(x):
        return ""
    return str(x).strip()

def url_to_basename(x):
    if pd.isna(x):
        return ""
    s = str(x).split("?")[0]
    return s.rsplit("/", 1)[-1]

def existing_files_map():
    return {p.name: p for p in out_dir.glob("*")}

def is_assigned(name, files):
    return name in files

def read_image_bytes(path):
    try:
        return path.read_bytes()
    except:
        return None

def delete_image(name):
    p = out_dir / name
    if p.exists():
        p.unlink()

# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:
    if st.button("Logout"):
        st.session_state["auth_ok"] = False
        st.rerun()

    st.divider()

    files = list(out_dir.glob("*"))
    if files:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for f in files:
                z.write(f, f.name)
        buf.seek(0)
        st.download_button("Scarica ZIP", buf, "images.zip")

    st.divider()

    if st.button("Svuota tutto"):
        shutil.rmtree(out_dir)
        out_dir.mkdir()
        st.rerun()

# =====================================================
# CSV
# =====================================================

st.title("Gestione immagini")

csv_file = st.file_uploader("Carica CSV", type=["csv"])
if not csv_file:
    st.stop()

df = pd.read_csv(csv_file)

image_cols = [c for c in df.columns if c.lower().startswith("image")]

rows = []

for _, row in df.iterrows():
    title = safe_str(row["Title"])
    brand = safe_str(row.get("Brand"))
    stagione = safe_str(row.get("Stagione"))
    tipo = safe_str(row.get("Type"))
    categoria = safe_str(row.get("Categoria"))
    reparto = safe_str(row.get("Reparto"))
    anno = safe_str(row.get("Anno"))
    colore = safe_str(row.get("Colore"))

    for col in image_cols:
        name = url_to_basename(row.get(col))
        if name:
            rows.append({
                "Title": title,
                "Brand": brand,
                "Stagione": stagione,
                "Type": tipo,
                "Categoria": categoria,
                "Reparto": reparto,
                "Anno": anno,
                "Colore": colore,
                "basename": name,
                "image_col": col
            })

all_df = pd.DataFrame(rows)

files_map = existing_files_map()

# =====================================================
# FILTRI
# =====================================================

st.subheader("Filtri")

title_q = st.text_input("Cerca titolo")

brands = st.multiselect("Brand", sorted(all_df["Brand"].unique()))
stagioni = st.multiselect("Stagione", sorted(all_df["Stagione"].unique()))
tipi = st.multiselect("Type", sorted(all_df["Type"].unique()))
categorie = st.multiselect("Categoria", sorted(all_df["Categoria"].unique()))
reparti = st.multiselect("Reparto", sorted(all_df["Reparto"].unique()))
anni = st.multiselect("Anno", sorted(all_df["Anno"].unique()))
colori = st.multiselect("Colore", sorted(all_df["Colore"].unique()))

filtered = all_df.copy()

if brands:
    filtered = filtered[filtered["Brand"].isin(brands)]
if stagioni:
    filtered = filtered[filtered["Stagione"].isin(stagioni)]
if tipi:
    filtered = filtered[filtered["Type"].isin(tipi)]
if categorie:
    filtered = filtered[filtered["Categoria"].isin(categorie)]
if reparti:
    filtered = filtered[filtered["Reparto"].isin(reparti)]
if anni:
    filtered = filtered[filtered["Anno"].isin(anni)]
if colori:
    filtered = filtered[filtered["Colore"].isin(colori)]
if title_q:
    filtered = filtered[filtered["Title"].str.contains(title_q, case=False)]

titles = sorted(filtered["Title"].unique())

selected = st.selectbox("Prodotto", titles)

prod_df = filtered[filtered["Title"] == selected]

# =====================================================
# HEADER
# =====================================================

st.markdown(f"## {selected}")

# =====================================================
# IMMAGINI
# =====================================================

for _, r in prod_df.iterrows():
    name = r["basename"]

    st.subheader(f'{r["image_col"]} {r["Colore"]} • {name}')

    c1, c2, c3 = st.columns(3)

    with c1:
        up = st.file_uploader("Upload", key=name)
        if up:
            (out_dir / name).write_bytes(up.getbuffer())
            st.rerun()

    with c2:
        if name in files_map:
            img = read_image_bytes(files_map[name])
            if img:
                st.image(img)

    with c3:
        if name in files_map:
            if st.button("🗑️ Elimina", key="del_"+name):
                delete_image(name)
                st.rerun()

st.success("OK")
