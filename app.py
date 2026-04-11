import io
import zipfile
import pandas as pd
import streamlit as st
from pathlib import Path
import shutil
from PIL import Image  # ✅ NUOVO

st.set_page_config(page_title="Elvira Image Assigner", layout="wide")

# =====================================================
# OTTIMIZZAZIONE IMMAGINI (NUOVO)
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
# LOGIN (UGUALE)
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
        st.write("")
        st.write("")
        st.write("")
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

def safe_str(x):
    if pd.isna(x): return ""
    s = str(x).strip()
    return "" if s.lower()=="nan" else s

def url_to_basename(x):
    if pd.isna(x): return ""
    s = str(x).strip()
    if not s: return ""
    s = s.split("?")[0]
    return s.rsplit("/",1)[-1]

def existing_files_map():
    return {p.name:p for p in out_dir.glob("*") if p.is_file()}

def is_assigned(b, existing):
    p = existing.get(b)
    return bool(p and p.exists())

def read_image_bytes(p):
    try: return p.read_bytes()
    except: return b""

def delete_image(b):
    p = out_dir / b
    if p.exists(): p.unlink()

# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:
    if st.button("Logout"):
        st.session_state["auth_ok"]=False
        st.rerun()

    st.divider()

    files = [p for p in out_dir.glob("*") if p.is_file()]
    if files:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf,"w") as z:
            for p in files:
                z.write(p, arcname=p.name)
        buf.seek(0)

        st.download_button("Scarica ZIP", buf, "images.zip")

    st.divider()

    if st.button("Svuota cartella"):
        shutil.rmtree(out_dir, ignore_errors=True)
        out_dir.mkdir(exist_ok=True)
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

rows = []
seen = set()

for _,row in df.iterrows():

    title = safe_str(row.get("Title",""))
    color = safe_str(row.get(color_col,""))
    color_code = safe_str(row.get(color_code_col,""))

    for col in image_cols:
        b = url_to_basename(row.get(col,""))
        if not b: continue

        key = (title,color,color_code,col,b)
        if key in seen: continue
        seen.add(key)

        rows.append({
            "Title":title,
            "Colore":color,
            "color_code":color_code,
            "image_col":col,
            "basename":b
        })

all_df = pd.DataFrame(rows)

existing_files = existing_files_map()

# =====================================================
# FILTRI
# =====================================================

color_map = all_df[["Colore","color_code"]].drop_duplicates().fillna("")

color_options = [
    f"{r['Colore']} ({r['color_code']})" if r["color_code"] else r["Colore"]
    for _,r in color_map.iterrows()
]

selected_color_labels = st.multiselect("Colore", color_options)

selected_colors = [c.split(" (")[0] for c in selected_color_labels]

filtered_df = all_df.copy()

if selected_colors:
    filtered_df = filtered_df[filtered_df["Colore"].isin(selected_colors)]

titles = sorted(filtered_df["Title"].unique())

selected_title = st.selectbox("Prodotto", titles)

prod_df = filtered_df[filtered_df["Title"]==selected_title]

# =====================================================
# UI
# =====================================================

for _,r in prod_df.iterrows():

    b = r["basename"]
    color = r["Colore"]
    code = r["color_code"]

    label = f"{color} ({code})" if code else color

    st.subheader(f"{r['image_col']} {label} • {b}")

    c1,c2,c3 = st.columns([1,1,0.5])

    with c1:
        up = st.file_uploader("Upload", key=b)
        if up:
            # 🔥 QUI AVVIENE L'OTTIMIZZAZIONE
            optimized = optimize_image(up)
            (out_dir / b).write_bytes(optimized.getvalue())
            st.success("Ottimizzata e salvata ✅")
            st.rerun()

    with c2:
        if is_assigned(b, existing_files):
            st.image(read_image_bytes(existing_files[b]))

    with c3:
        if is_assigned(b, existing_files):
            if st.button("Elimina", key="del"+b):
                delete_image(b)
                st.rerun()
