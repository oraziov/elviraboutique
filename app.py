import io
import zipfile
import pandas as pd
import streamlit as st
from pathlib import Path
import shutil

st.set_page_config(page_title="Elvira Image Assigner", layout="wide")

# =====================================================
# LOGIN (ROBUSTO, CENTRATO, STREAMLIT-NATIVE)
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
        except:
            return 999
    return 999

def existing_files_map() -> dict:
    return {p.name: p for p in out_dir.glob("*") if p.is_file()}

def is_assigned(basename: str, existing_files: dict) -> bool:
    p = existing_files.get(basename)
    return bool(p and p.exists())

def first_incomplete_title(all_df: pd.DataFrame, existing_files: dict):
    for t in sorted(all_df["Title"].unique()):
        sub = all_df[all_df["Title"] == t]
        if any(not is_assigned(b, existing_files) for b in sub["basename"].tolist()):
            return t
    return None

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
    files = list(out_dir.glob("*"))
    if files:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for p in files:
                if p.is_file():
                    z.write(p, arcname=p.name)
        buf.seek(0)
        st.download_button(
            "⬇️ Scarica ZIP",
            buf,
            "output_images.zip",
            "application/zip",
            use_container_width=True
        )
        st.caption(f"File nello ZIP: {len([p for p in files if p.is_file()])}")
    else:
        st.info("Nessuna immagine salvata")

    st.divider()

    st.subheader("Pulizia")
    if st.button("🗑️ Svuota output_images", use_container_width=True):
        st.session_state["confirm_delete"] = True

    if st.session_state.get("confirm_delete"):
        st.warning("Confermi di eliminare TUTTE le immagini salvate?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Conferma", use_container_width=True):
                shutil.rmtree(out_dir, ignore_errors=True)
                out_dir.mkdir(exist_ok=True)
                st.session_state["confirm_delete"] = False
                st.success("output_images svuotata")
                st.rerun()
        with c2:
            if st.button("❌ Annulla", use_container_width=True):
                st.session_state["confirm_delete"] = False
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

# Prendo tutte le colonne Image* (Image1, Image2, ...)
image_cols = [c for c in df.columns if c.lower().startswith("image")]
if not image_cols:
    st.error("Nessuna colonna Image trovata")
    st.stop()

if "Title" not in df.columns:
    st.error("Colonna Title mancante")
    st.stop()

color_col = "Colore" if "Colore" in df.columns else None

# Costruisco righe uniche: Title + Colore + ImageX + basename
rows = []
seen = set()

for _, row in df.iterrows():
    title = str(row["Title"]).strip()
    if not title or title.lower() == "nan":
        continue

    color = str(row.get(color_col, "")).strip() if color_col else ""
    if color.lower() == "nan":
        color = ""

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
            "basename": basename
        })

all_df = pd.DataFrame(rows)
if all_df.empty:
    st.warning("Non ho trovato nessun nome immagine nelle colonne Image*.")
    st.stop()

all_df["order"] = all_df["image_col"].apply(sort_image_col)
all_df = all_df.sort_values(["Title", "Colore", "order", "basename"]).drop(columns=["order"])

# Stato file presenti
existing_files = existing_files_map()

# Navigazione: prossimo prodotto incompleto + filtro colori incompleti
nav_col1, nav_col2 = st.columns([2, 1])

with nav_col1:
    show_only_incomplete_colors = st.checkbox("Mostra solo colori incompleti", value=True)

with nav_col2:
    if st.button("➡️ Prossimo prodotto incompleto", use_container_width=True):
        nxt = first_incomplete_title(all_df, existing_files)
        if nxt:
            st.session_state["selected_title"] = nxt
            st.rerun()
        else:
            st.success("Tutti i prodotti sono completi ✅")

titles = sorted(all_df["Title"].unique())
if "selected_title" not in st.session_state:
    st.session_state["selected_title"] = titles[0]

selected_title = st.selectbox(
    "Seleziona Titolo",
    titles,
    index=(titles.index(st.session_state["selected_title"]) if st.session_state["selected_title"] in titles else 0),
)

st.session_state["selected_title"] = selected_title

prod_df = all_df[all_df["Title"] == selected_title].copy()

# Colori del titolo
colors = sorted(prod_df["Colore"].fillna("").unique(), key=lambda x: (x == "", x))

# UI per colore
for color in colors:
    label = color if color else "SENZA COLORE"

    sub = prod_df[prod_df["Colore"].fillna("") == (color or "")].copy()

    assigned_flags = [is_assigned(b, existing_files) for b in sub["basename"].tolist()]
    total_count = len(assigned_flags)
    missing_count = assigned_flags.count(False)

    if show_only_incomplete_colors and missing_count == 0:
        continue

    # Header colore + badge stato
    h1, h2 = st.columns([3, 2])
    with h1:
        st.header(f"Colore: {label}")
    with h2:
        if missing_count == 0:
            st.success("COMPLETO ✅")
        else:
            st.warning(f"Mancano {missing_count} / {total_count}")

    if total_count > 0:
        st.progress((total_count - missing_count) / total_count)

    # Righe immagini
    for _, r in sub.iterrows():
        basename = r["basename"]
        image_col = r["image_col"]

        # ✅ richiesta: "Image1 Nero"
        st.subheader(f"{image_col} {label} • {basename}")

        c1, c2 = st.columns([1, 1])

        with c1:
            up = st.file_uploader(
                f"Carica file per {basename}",
                type=["jpg", "jpeg", "png", "webp"],
                key=f"{selected_title}_{label}_{basename}",
            )
            if up:
                (out_dir / basename).write_bytes(up.getbuffer())
                existing_files[basename] = out_dir / basename
                st.success("Salvato ✅")
                st.rerun()

        with c2:
            if is_assigned(basename, existing_files):
                st.image(str(existing_files[basename]), use_container_width=True)
            else:
                st.info("Non ancora assegnata")

        st.divider()

st.success("Sistema pronto")
