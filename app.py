import io
import zipfile
import pandas as pd
import streamlit as st
from pathlib import Path
import shutil

st.set_page_config(page_title="Elvira Image Assigner", layout="wide")

# =====================================================
# LOGIN (ROBUSTO)
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

            pwd = st.text_input("Password", type="password", placeholder="Inserisci password")

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

def safe_str(x) -> str:
    if pd.isna(x):
        return ""
    s = str(x).strip()
    return "" if s.lower() == "nan" else s

def url_to_basename(x: str) -> str:
    if pd.isna(x):
        return ""
    s = str(x).strip()
    if not s or s.lower() == "nan":
        return ""
    s = s.split("?")[0]
    return s.rsplit("/", 1)[-1]

def sort_image_col(col: str) -> int:
    c = (col or "").lower().strip()
    if c.startswith("image"):
        try:
            return int(c.replace("image", ""))
        except Exception:
            return 999
    return 999

def existing_files_map() -> dict:
    return {p.name: p for p in out_dir.glob("*") if p.is_file()}

def is_assigned(basename: str, existing_files: dict) -> bool:
    p = existing_files.get(basename)
    return bool(p and p.exists())

def first_incomplete_title(df_titles: pd.DataFrame, existing_files: dict):
    for t in sorted(df_titles["Title"].unique()):
        sub = df_titles[df_titles["Title"] == t]
        if any(not is_assigned(b, existing_files) for b in sub["basename"].tolist()):
            return t
    return None

def read_image_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except Exception:
        return b""

def delete_image(basename: str):
    p = out_dir / basename
    if p.exists() and p.is_file():
        p.unlink()

# =====================================================
# APP
# =====================================================

st.title("Gestione immagini prodotti")

csv_file = st.file_uploader("Carica CSV prodotti", type=["csv"])
if not csv_file:
    st.info("Carica un CSV per iniziare")
    st.stop()

df = pd.read_csv(csv_file)

if "Title" not in df.columns:
    st.error("Colonna Title mancante")
    st.stop()

image_cols = [c for c in df.columns if c.lower().startswith("image")]
if not image_cols:
    st.error("Nessuna colonna Image trovata")
    st.stop()

color_col = "Colore" if "Colore" in df.columns else None
color_code_col = "Color_code" if "Color_code" in df.columns else None
brand_col = "Brand" if "Brand" in df.columns else None
season_col = "Stagione" if "Stagione" in df.columns else None
type_col = "Type" if "Type" in df.columns else None

rows = []
seen = set()

for _, row in df.iterrows():
    title = safe_str(row.get("Title", ""))
    if not title:
        continue

    color = safe_str(row.get(color_col, "")) if color_col else ""
    color_code = safe_str(row.get(color_code_col, "")) if color_code_col else ""
    brand = safe_str(row.get(brand_col, "")) if brand_col else ""
    season = safe_str(row.get(season_col, "")) if season_col else ""
    ptype = safe_str(row.get(type_col, "")) if type_col else ""

    for col in image_cols:
        raw = row.get(col, "")
        basename = url_to_basename(raw)
        if not basename:
            continue

        key = (title, color, color_code, brand, season, ptype, col, basename)
        if key in seen:
            continue
        seen.add(key)

        rows.append({
            "Title": title,
            "Colore": color,
            "Color_code": color_code,
            "Brand": brand,
            "Stagione": season,
            "Type": ptype,
            "image_col": col,
            "basename": basename
        })

all_df = pd.DataFrame(rows)

# =====================================================
# FILTRO COLORE CON COLOR CODE
# =====================================================

color_map = (
    all_df[["Colore", "Color_code"]]
    .drop_duplicates()
    .fillna("")
)

color_options = [
    f"{row['Colore']} ({row['Color_code']})" if row["Color_code"] else row["Colore"]
    for _, row in color_map.iterrows()
]

selected_color_labels = st.multiselect("Colore", color_options, default=[])

selected_colors = [c.split(" (")[0] for c in selected_color_labels]

# =====================================================
# FILTRO BASE
# =====================================================

filtered_df = all_df.copy()

if selected_colors:
    filtered_df = filtered_df[filtered_df["Colore"].isin(selected_colors)]

titles = sorted(filtered_df["Title"].unique())

selected_title = st.selectbox("Seleziona Titolo", titles)

prod_df = filtered_df[filtered_df["Title"] == selected_title]

existing_files = existing_files_map()

# =====================================================
# UI
# =====================================================

for _, r in prod_df.iterrows():
    basename = r["basename"]
    image_col = r["image_col"]

    st.subheader(f"{image_col} {r['Colore']} • {basename}")

    c1, c2, c3 = st.columns([1, 1, 0.5])

    with c1:
        up = st.file_uploader("Carica", key=basename)
        if up:
            (out_dir / basename).write_bytes(up.getbuffer())
            st.rerun()

    with c2:
        if basename in existing_files:
            st.image(read_image_bytes(existing_files[basename]))

    with c3:
        if basename in existing_files:
            if st.button("🗑️", key=f"del_{basename}"):
                delete_image(basename)
                st.rerun()

st.success("Sistema pronto")
