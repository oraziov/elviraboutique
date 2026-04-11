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

    left, center, right = st.columns([1, 1.2, 1])

    with center:
        st.write("")
        st.write("")
        st.write("")
        with st.container(border=True):
            try:
                st.image("elvira_logo.png", use_container_width=True)
            except Exception:
                pass

            st.markdown("## Elvira Image Assigner")
            st.caption("Accesso riservato")

            pwd = st.text_input("Password", type="password")

            c1, c2 = st.columns(2)
            with c1:
                login = st.button("Accedi", use_container_width=True)
            with c2:
                clear = st.button("Pulisci", use_container_width=True)

            if clear:
                st.rerun()

            if login:
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

def sort_image_col(col):
    c = (col or "").lower().strip()
    if c.startswith("image"):
        try:
            return int(c.replace("image", ""))
        except:
            return 999
    return 999

def existing_files_map():
    return {p.name: p for p in out_dir.glob("*") if p.is_file()}

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

        st.download_button(
            "⬇️ Scarica ZIP",
            buf,
            "output_images.zip",
            "application/zip",
            use_container_width=True,
        )
        st.caption(f"{len(files)} file")
    else:
        st.info("Nessuna immagine salvata")

    st.divider()

    if st.button("🗑️ Svuota output_images", use_container_width=True):
        shutil.rmtree(out_dir, ignore_errors=True)
        out_dir.mkdir(exist_ok=True)
        st.success("Pulito")
        st.rerun()

# =====================================================
# APP
# =====================================================

st.title("Gestione immagini prodotti")

csv_file = st.file_uploader("Carica CSV", type=["csv"])
if not csv_file:
    st.stop()

df = pd.read_csv(csv_file)

if "Title" not in df.columns:
    st.error("Colonna Title mancante")
    st.stop()

image_cols = [c for c in df.columns if c.lower().startswith("image")]
if not image_cols:
    st.error("Nessuna colonna Image")
    st.stop()

color_col = "Colore" if "Colore" in df.columns else None
color_code_col = "color_code" if "color_code" in df.columns else None

rows = []
seen = set()

for _, row in df.iterrows():
    title = safe_str(row.get("Title"))
    if not title:
        continue

    color = safe_str(row.get(color_col)) if color_col else ""
    color_code = safe_str(row.get(color_code_col)) if color_code_col else ""

    for col in image_cols:
        basename = url_to_basename(row.get(col))
        if not basename:
            continue

        key = (title, color, col, basename)
        if key in seen:
            continue
        seen.add(key)

        rows.append({
            "Title": title,
            "Colore": color,
            "ColorCode": color_code,
            "image_col": col,
            "basename": basename
        })

all_df = pd.DataFrame(rows)

all_df["order"] = all_df["image_col"].apply(sort_image_col)
all_df = all_df.sort_values(["Title", "Colore", "order"]).drop(columns=["order"])

# =====================================================
# 🔍 FILTRO COLOR CODE
# =====================================================

color_codes = sorted([c for c in all_df["ColorCode"].unique() if c])

selected_color_code = st.selectbox(
    "Filtra per Color Code",
    ["Tutti"] + color_codes
)

filtered_df = all_df.copy()

if selected_color_code != "Tutti":
    filtered_df = filtered_df[
        filtered_df["ColorCode"] == selected_color_code
    ]

# =====================================================
# UI
# =====================================================

titles = sorted(filtered_df["Title"].unique())

if not titles:
    st.warning("Nessun risultato con questo filtro")
    st.stop()

selected_title = st.selectbox("Seleziona Titolo", titles)

prod_df = filtered_df[filtered_df["Title"] == selected_title]

for color in prod_df["Colore"].unique():
    sub = prod_df[prod_df["Colore"] == color]

    color_code_val = sub["ColorCode"].iloc[0]

    color_dot = ""
    if color_code_val:
        color_dot = f"""
        <span style="
            display:inline-block;
            width:16px;
            height:16px;
            background:{color_code_val};
            border-radius:50%;
            border:1px solid #ccc;
            margin-left:8px;
        "></span>
        """

    st.markdown(f"## {color} {color_dot}", unsafe_allow_html=True)

    for idx, r in sub.iterrows():
        basename = r["basename"]

        col1, col2 = st.columns(2)

        key = f"{selected_title}_{color}_{basename}_{idx}"

        with col1:
            up = st.file_uploader("Upload", key=key)
            if up:
                (out_dir / basename).write_bytes(up.getbuffer())
                st.rerun()

        with col2:
            path = out_dir / basename
            if path.exists():
                st.image(str(path))
