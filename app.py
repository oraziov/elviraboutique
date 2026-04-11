import io
import zipfile
import pandas as pd
import streamlit as st
from pathlib import Path
import shutil
from PIL import Image
import difflib

st.set_page_config(page_title="Elvira Image Assigner", layout="wide")

# =====================================================
# LOGIN
# =====================================================

def require_password():
    if st.session_state.get("auth_ok"):
        return True

    st.markdown(
        """
        <style>
          #MainMenu {visibility: hidden;}
          footer {visibility: hidden;}
          header {visibility: hidden;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    center = st.columns([1,1.2,1])[1]

    with center:
        with st.container(border=True):
            st.markdown("## Elvira Image Assigner")
            pwd = st.text_input("Password", type="password")

            if st.button("Accedi"):
                if pwd == st.secrets.get("APP_PASSWORD", ""):
                    st.session_state["auth_ok"] = True
                    st.rerun()
                else:
                    st.error("Password errata")

    return False


if not require_password():
    st.stop()

# =====================================================
# CONFIG
# =====================================================

out_dir = Path("output_images")
out_dir.mkdir(exist_ok=True)

# =====================================================
# IMAGE PROCESSING (SHOPIFY READY)
# =====================================================

def process_image(file_bytes, max_size=(2048, 2048), quality=85, max_kb=250):
    img = Image.open(io.BytesIO(file_bytes))

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    img.thumbnail(max_size)

    output = io.BytesIO()

    while quality > 30:
        output.seek(0)
        img.save(output, format="JPEG", quality=quality, optimize=True)
        size_kb = len(output.getvalue()) / 1024

        if size_kb <= max_kb:
            break

        quality -= 5

    return output.getvalue()

# =====================================================
# HELPERS
# =====================================================

def safe_str(x):
    if pd.isna(x):
        return ""
    s = str(x).strip()
    return "" if s.lower() == "nan" else s

def url_to_basename(x):
    if pd.isna(x):
        return ""
    s = str(x).split("?")[0]
    return s.rsplit("/", 1)[-1]

def existing_files_map():
    return {p.name: p for p in out_dir.glob("*")}

def is_assigned(basename, existing):
    return basename in existing

# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:

    if st.button("Logout"):
        st.session_state["auth_ok"] = False
        st.rerun()

    st.divider()

    # DOWNLOAD ZIP
    files = list(out_dir.glob("*"))
    if files:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for f in files:
                z.write(f, f.name)

        st.download_button("Scarica ZIP", buf.getvalue(), "images.zip")

    st.divider()

    # ZIP IMPORT
    st.subheader("Importa ZIP")

    zip_file = st.file_uploader("Carica ZIP", type=["zip"])

    if zip_file:
        with zipfile.ZipFile(zip_file) as z:

            existing = existing_files_map()
            names = list(all_df["basename"].values) if "all_df" in globals() else []

            total = len(z.namelist())
            progress = st.progress(0)

            matched = 0

            for i, file_name in enumerate(z.namelist()):
                progress.progress((i+1)/total)

                if file_name.endswith("/"):
                    continue

                basename = Path(file_name).name
                file_bytes = z.read(file_name)

                processed = process_image(file_bytes)

                # match diretto
                if basename in names:
                    (out_dir / basename).write_bytes(processed)
                    matched += 1
                else:
                    # fuzzy match
                    match = difflib.get_close_matches(basename, names, n=1, cutoff=0.8)
                    if match:
                        (out_dir / match[0]).write_bytes(processed)
                        matched += 1

            st.success(f"Import completato - Match: {matched}")
            st.rerun()

    st.divider()

    # CLEAN
    if st.button("Svuota immagini"):
        shutil.rmtree(out_dir, ignore_errors=True)
        out_dir.mkdir(exist_ok=True)
        st.rerun()

# =====================================================
# MAIN
# =====================================================

st.title("Gestione immagini prodotti")

csv_file = st.file_uploader("Carica CSV", type=["csv"])

if not csv_file:
    st.stop()

df = pd.read_csv(csv_file)

image_cols = [c for c in df.columns if c.lower().startswith("image")]

rows = []

for _, row in df.iterrows():

    for col in image_cols:
        basename = url_to_basename(row[col])

        if basename:
            rows.append({
                "Title": safe_str(row["Title"]),
                "Colore": safe_str(row.get("Colore")),
                "ColorCode": safe_str(row.get("color_code")),
                "basename": basename
            })

all_df = pd.DataFrame(rows)

existing = existing_files_map()

titles = sorted(all_df["Title"].unique())

selected_title = st.selectbox("Prodotto", titles)

prod = all_df[all_df["Title"] == selected_title]

# =====================================================
# UI
# =====================================================

for color in prod["Colore"].unique():

    sub = prod[prod["Colore"] == color]

    code = sub["ColorCode"].iloc[0]

    color_html = f"""
    <span style="background:{code};width:16px;height:16px;display:inline-block;border-radius:50%"></span>
    """ if code else ""

    st.markdown(f"## {color} {color_html}", unsafe_allow_html=True)

    for _, r in sub.iterrows():

        basename = r["basename"]

        col1, col2, col3 = st.columns([1,1,0.5])

        with col1:
            up = st.file_uploader(f"Upload {basename}", key=basename)

            if up:
                processed = process_image(up.getbuffer())
                (out_dir / basename).write_bytes(processed)
                st.rerun()

        with col2:
            if basename in existing:
                st.image(str(out_dir / basename))

        with col3:
            if basename in existing:
                if st.button("Elimina", key=f"del_{basename}"):
                    (out_dir / basename).unlink()
                    st.rerun()

st.success("Pronto 🚀")
