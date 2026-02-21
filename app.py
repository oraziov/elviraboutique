import io
import zipfile
import pandas as pd
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Elvira Image Assigner", layout="wide")

# =====================================================
# LOGIN PROFESSIONALE CON LOGO
# =====================================================

def login_screen():
    st.markdown(
        """
        <style>
          .login-wrap { min-height: 95vh; display: flex; align-items: center; justify-content: center; }
          .login-card { width: 420px; max-width: 92vw; padding: 30px; border-radius: 18px;
                        border: 1px solid rgba(0,0,0,0.08); background: white;
                        box-shadow: 0 15px 40px rgba(0,0,0,0.08); }
          .login-title { text-align: center; font-size: 1.4rem; font-weight: 700; margin: 10px 0 4px; }
          .login-sub { text-align: center; opacity: .6; margin-bottom: 20px; }
          .login-footer { text-align: center; opacity: .5; font-size: .8rem; margin-top: 15px; }
          #MainMenu {visibility: hidden;}
          footer {visibility: hidden;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="login-wrap"><div class="login-card">', unsafe_allow_html=True)

    # LOGO dalla repo (deve chiamarsi elvira_logo.png)
    st.image("elvira_logo.png", width=150)

    st.markdown('<div class="login-title">Elvira Image Assigner</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-sub">Accesso riservato</div>', unsafe_allow_html=True)

    pwd = st.text_input("Password", type="password", key="login_pwd", label_visibility="collapsed", placeholder="Password")
    btn = st.button("Accedi", use_container_width=True)

    if btn:
        if pwd == st.secrets.get("APP_PASSWORD", ""):
            st.session_state["auth_ok"] = True
            st.rerun()
        else:
            st.error("Password errata")

    st.markdown('<div class="login-footer">© Elvira</div>', unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)


if "auth_ok" not in st.session_state or not st.session_state["auth_ok"]:
    login_screen()
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
