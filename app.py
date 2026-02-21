import io
import zipfile
import pandas as pd
import streamlit as st
from pathlib import Path
import shutil

st.set_page_config(page_title="Elvira Image Assigner", layout="wide")

# =====================================================
# LOGIN DARK PROFESSIONALE
# =====================================================

def require_password():

    if st.session_state.get("auth_ok"):
        return True

    st.markdown(
        """
        <style>
        .block-container {padding-top: 0rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        .login-wrapper {
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .login-box {
            background-color: #111827;
            padding: 40px;
            border-radius: 16px;
            width: 420px;
            box-shadow: 0px 20px 60px rgba(0,0,0,0.4);
            text-align: center;
        }

        .login-title {
            font-size: 22px;
            font-weight: 600;
            margin-top: 15px;
            color: white;
        }

        .login-sub {
            font-size: 14px;
            opacity: 0.6;
            margin-bottom: 25px;
            color: white;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="login-wrapper"><div class="login-box">', unsafe_allow_html=True)

    try:
        st.image("elvira_logo.png", width=160)
    except:
        pass

    st.markdown('<div class="login-title">Elvira Image Assigner</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-sub">Accesso riservato</div>', unsafe_allow_html=True)

    pwd = st.text_input("Password", type="password", label_visibility="collapsed")

    if st.button("Accedi", use_container_width=True):
        if pwd == st.secrets.get("APP_PASSWORD", ""):
            st.session_state["auth_ok"] = True
            st.rerun()
        else:
            st.error("Password errata")

    st.markdown("</div></div>", unsafe_allow_html=True)

    return False


if not require_password():
    st.stop()

# =====================================================
# APP PRINCIPALE
# =====================================================

st.title("Gestione immagini prodotti")

# Cartella immagini
out_dir = Path("output_images")
out_dir.mkdir(exist_ok=True)

# Sidebar controlli
with st.sidebar:

    st.subheader("Gestione sessione")

    if st.button("🚪 Logout"):
        st.session_state["auth_ok"] = False
        st.rerun()

    st.divider()

    st.subheader("Download immagini")

    files = list(out_dir.glob("*"))
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
        )
    else:
        st.info("Nessuna immagine salvata")

    st.divider()

    st.subheader("Pulizia")

    if st.button("🗑️ Svuota output_images"):
        st.session_state["confirm_delete"] = True

    if st.session_state.get("confirm_delete"):
        st.warning("Sei sicuro di voler eliminare TUTTE le immagini?")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("✅ Conferma eliminazione"):
                shutil.rmtree(out_dir)
                out_dir.mkdir(exist_ok=True)
                st.session_state["confirm_delete"] = False
                st.success("Cartella svuotata")
                st.rerun()

        with col2:
            if st.button("❌ Annulla"):
                st.session_state["confirm_delete"] = False
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
# CSV
# =====================================================

csv_file = st.file_uploader("Carica CSV prodotti", type=["csv"])

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

st.success("Sistema pronto ✅")
