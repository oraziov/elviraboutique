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
        st.caption(f"File nello ZIP: {len(files)}")
    else:
        st.info("Nessuna immagine salvata")

    st.divider()

    st.subheader("Pulizia")
    if st.button("🗑️ Svuota output_images", use_container_width=True):
        st.session_state["confirm_delete_all"] = True

    if st.session_state.get("confirm_delete_all"):
        st.warning("Confermi di eliminare TUTTE le immagini salvate?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Conferma", use_container_width=True):
                shutil.rmtree(out_dir, ignore_errors=True)
                out_dir.mkdir(exist_ok=True)
                st.session_state["confirm_delete_all"] = False
                st.success("output_images svuotata")
                st.rerun()
        with c2:
            if st.button("❌ Annulla", use_container_width=True):
                st.session_state["confirm_delete_all"] = False
                st.rerun()

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

color_map = all_df[["Colore", "Color_code"]].drop_duplicates().fillna("")

color_options = [
    f"{row['Colore']} ({row['Color_code']})" if row["Color_code"] else row["Colore"]
    for _, row in color_map.iterrows()
]

# =====================================================
# FILTRI
# =====================================================

brands = sorted([b for b in all_df["Brand"].dropna().unique().tolist() if str(b).strip()])
seasons = sorted([s for s in all_df["Stagione"].dropna().unique().tolist() if str(s).strip()])
types = sorted([t for t in all_df["Type"].dropna().unique().tolist() if str(t).strip()])

f1, f2, f3, f4 = st.columns([1, 1, 1, 1])
with f1:
    selected_brands = st.multiselect("Brand", brands, default=[])
with f2:
    selected_seasons = st.multiselect("Stagione", seasons, default=[])
with f3:
    selected_types = st.multiselect("Type / Categoria", types, default=[])
with f4:
    selected_color_labels = st.multiselect("Colore", color_options, default=[])

selected_colors = [c.split(" (")[0] for c in selected_color_labels]

# resto codice IDENTICO (filtri, UI, eliminazione ecc.)
