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
# SETUP
# =====================================================

out_dir = Path("output_images")
out_dir.mkdir(exist_ok=True)

# =====================================================
# IMAGE PROCESSING (SHOPIFY)
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
        if len(output.getvalue()) / 1024 <= max_kb:
            break
        quality -= 5

    return output.getvalue()

# =====================================================
# HELPERS
# =====================================================

def safe_str(x):
    if pd.isna(x):
        return ""
    return str(x).strip()

def url_to_basename(x):
    if pd.isna(x):
        return ""
    return str(x).split("?")[0].rsplit("/", 1)[-1]

def existing_files_map():
    return {p.name: p for p in out_dir.glob("*")}

def is_assigned(basename, existing):
    return basename in existing

def delete_image(basename):
    p = out_dir / basename
    if p.exists():
        p.unlink()

# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:

    if st.button("🚪 Logout"):
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

        st.download_button("⬇️ Scarica ZIP", buf.getvalue(), "images.zip")

    st.divider()

    # IMPORT MULTI / ZIP
    st.subheader("📦 Import immagini")

    uploaded_files = st.file_uploader(
        "Trascina immagini o ZIP",
        type=["jpg", "jpeg", "png", "webp", "zip"],
        accept_multiple_files=True
    )

    if uploaded_files and "all_df" in globals():

        names = all_df["basename"].tolist()
        matched, skipped = 0, 0
        unmatched = []

        inputs = []

        for f in uploaded_files:
            if f.name.endswith(".zip"):
                with zipfile.ZipFile(f) as z:
                    for name in z.namelist():
                        if not name.endswith("/"):
                            inputs.append((Path(name).name, z.read(name)))
            else:
                inputs.append((f.name, f.getbuffer()))

        progress = st.progress(0)

        for i, (filename, file_bytes) in enumerate(inputs):
            progress.progress((i+1)/len(inputs))

            basename = Path(filename).name
            target = out_dir / basename

            if target.exists():
                skipped += 1
                continue

            processed = process_image(file_bytes)

            if basename in names:
                target.write_bytes(processed)
                matched += 1
            else:
                match = difflib.get_close_matches(basename, names, 1, 0.8)
                if match:
                    (out_dir / match[0]).write_bytes(processed)
                    matched += 1
                else:
                    unmatched.append(basename)

        st.success(f"✅ Match: {matched}")
        st.info(f"⏭️ Skipped: {skipped}")

        if unmatched:
            st.warning(f"❌ Non associati: {len(unmatched)}")

        st.rerun()

    st.divider()

    if st.button("🗑️ Svuota immagini"):
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

    color_dot = f"""
    <span style="
        background:{code};
        width:16px;height:16px;
        display:inline-block;
        border-radius:50%;
        margin-left:8px"></span>
    """ if code else ""

    st.markdown(f"## {color} {color_dot}", unsafe_allow_html=True)

    for idx, r in sub.iterrows():

        basename = r["basename"]

        col1, col2, col3 = st.columns([1,1,0.6])

        unique_key = f"{selected_title}_{color}_{basename}_{idx}"

        with col1:
            up = st.file_uploader("Upload", key=unique_key)

            if up:
                processed = process_image(up.getbuffer())
                (out_dir / basename).write_bytes(processed)
                st.rerun()

        with col2:
            if basename in existing:
                st.image(str(out_dir / basename))
            else:
                st.info("Non assegnata")

        with col3:
            if basename in existing:
                if st.button("🗑️", key=f"del_{unique_key}"):
                    delete_image(basename)
                    st.rerun()

st.success("Sistema pronto 🚀")
