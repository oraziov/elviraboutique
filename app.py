import io
import zipfile
import pandas as pd
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Elvira Image Assigner", layout="wide")

# =====================================================
# LOGIN PROFESSIONALE CON LOGO
# =====================================================


def require_password():
    # CSS minimale (niente HTML card)
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

    if st.session_state.get("auth_ok"):
        return True

    # Centra con columns (super stabile)
    left, mid, right = st.columns([1, 2, 1], vertical_alignment="center")

    with mid:
        st.markdown("<div style='height: 10vh'></div>", unsafe_allow_html=True)

        # Logo (se manca, non rompe la pagina)
        try:
            st.image("elvira_logo.png", use_container_width=True)
        except Exception:
            st.markdown("")

        st.markdown(
            "<h2 style='text-align:center; margin-top:10px;'>Elvira Image Assigner</h2>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align:center; opacity:0.7; margin-top:-8px;'>Accesso riservato</p>",
            unsafe_allow_html=True,
        )

        pwd = st.text_input("Password", type="password", placeholder="Inserisci password")

        c1, c2 = st.columns([1, 1])
        with c1:
            login = st.button("Accedi", use_container_width=True)
        with c2:
            clear = st.button("Pulisci", use_container_width=True)

        if clear:
            st.session_state.pop("pwd_tmp", None)
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
# APP PRINCIPALE
# =====================================================

st.title("Gestione immagini prodotti (Titolo + Colore)")

# Logout
with st.sidebar:
    if st.button("🚪 Logout"):
        st.session_state["auth_ok"] = False
        st.rerun()

# =====================================================
# FUNZIONI
# =====================================================

def url_to_basename(x: str) -> str:
    if pd.isna(x):
        return ""
    s = str(x).strip()
    if not s:
        return ""
    s = s.split("?")[0]
    return s.rsplit("/", 1)[-1]

def sort_image_col(col: str) -> int:
    c = col.lower()
    if c.startswith("image"):
        try:
            return int(c.replace("image", ""))
        except:
            return 999
    return 999

# =====================================================
# UPLOAD CSV
# =====================================================

csv_file = st.file_uploader("Carica CSV prodotti", type=["csv"])
out_dir = Path("output_images")
out_dir.mkdir(exist_ok=True)

# ZIP download sidebar
with st.sidebar:
    st.subheader("Download immagini")
    files = list(out_dir.glob("*"))
    if files:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for p in files:
                z.write(p, arcname=p.name)
        buf.seek(0)
        st.download_button("⬇️ Scarica ZIP", buf, "output_images.zip", "application/zip")
    else:
        st.info("Nessuna immagine salvata")

if not csv_file:
    st.info("Carica un CSV per iniziare")
    st.stop()

df = pd.read_csv(csv_file)

image_cols = [c for c in df.columns if c.lower().startswith("image")]
if not image_cols:
    st.error("Nessuna colonna Image trovata")
    st.stop()

if "Title" not in df.columns:
    st.error("Colonna Title mancante")
    st.stop()

color_col = "Colore" if "Colore" in df.columns else None

rows = []
seen = set()

for _, row in df.iterrows():
    title = str(row["Title"]).strip()
    color = str(row.get(color_col, "")).strip() if color_col else ""

    for col in image_cols:
        raw = row.get(col, "")
        basename = url_to_basename(raw)
        if not basename:
            continue

        key = (title, color, col, basename)
        if key in seen:
            continue
        seen.add(key)

        rows.append({
            "Title": title,
            "Colore": color,
            "image_col": col,
            "basename": basename,
            "image_url": raw
        })

all_df = pd.DataFrame(rows)
all_df["order"] = all_df["image_col"].apply(sort_image_col)
all_df = all_df.sort_values(["Title", "Colore", "order"]).drop(columns=["order"])

titles = sorted(all_df["Title"].unique())
selected_title = st.selectbox("Seleziona Titolo", titles)

prod_df = all_df[all_df["Title"] == selected_title]

existing_files = {p.name: p for p in out_dir.glob("*")}

colors = sorted(prod_df["Colore"].fillna("").unique())

for color in colors:
    label = color if color else "SENZA COLORE"
    st.header(f"Colore: {label}")

    sub = prod_df[prod_df["Colore"].fillna("") == (color or "")]

    urls = [u for u in sub["image_url"] if isinstance(u, str) and u.strip()]
    if urls:
        st.image(urls[:3], use_container_width=True)

    for _, r in sub.iterrows():
        basename = r["basename"]
        st.subheader(f"{r['image_col']} • {basename}")

        c1, c2 = st.columns(2)

        with c1:
            up = st.file_uploader(
                f"Carica file per {basename}",
                type=["jpg", "jpeg", "png", "webp"],
                key=f"{basename}"
            )
            if up:
                (out_dir / basename).write_bytes(up.getbuffer())
                existing_files[basename] = out_dir / basename
                st.success("Salvato")

        with c2:
            if basename in existing_files:
                st.image(str(existing_files[basename]), use_container_width=True)
            else:
                st.info("Non ancora assegnata")

st.success("App pronta ✅")
