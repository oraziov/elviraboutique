import io
import zipfile
import pandas as pd
import streamlit as st
from pathlib import Path
import shutil

st.set_page_config(page_title="Elvira Image Assigner", layout="wide")

# ================= LOGIN =================

def require_password():
    if st.session_state.get("auth_ok"):
        return True

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

# ================= SETUP =================

out_dir = Path("output_images")
out_dir.mkdir(exist_ok=True)

def safe(x):
    return "" if pd.isna(x) else str(x).strip()

def url_to_basename(x):
    s = safe(x)
    if not s: return ""
    return s.split("?")[0].rsplit("/", 1)[-1]

def existing_files():
    return {p.name: p for p in out_dir.glob("*")}

def is_assigned(name, files):
    return name in files

def read_img(p):
    try: return p.read_bytes()
    except: return None

def delete_img(name):
    p = out_dir / name
    if p.exists(): p.unlink()

# ================= SIDEBAR =================

with st.sidebar:
    if st.button("🚪 Logout"):
        st.session_state["auth_ok"] = False
        st.rerun()

    st.divider()

    files = list(out_dir.glob("*"))
    if files:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for p in files:
                z.write(p, p.name)
        buf.seek(0)
        st.download_button("⬇️ ZIP", buf, "images.zip")

    st.divider()

    if st.button("🗑️ Svuota tutto"):
        shutil.rmtree(out_dir, ignore_errors=True)
        out_dir.mkdir()
        st.rerun()

# ================= CSV =================

st.title("Gestione immagini prodotti")

csv = st.file_uploader("CSV", type="csv")
if not csv:
    st.stop()

df = pd.read_csv(csv)

image_cols = [c for c in df.columns if c.lower().startswith("image")]

rows = []
seen = set()

for _, r in df.iterrows():
    title = safe(r.get("Title"))
    color = safe(r.get("Colore"))
    code = safe(r.get("color_code"))
    brand = safe(r.get("Brand"))
    season = safe(r.get("Stagione"))
    typ = safe(r.get("Type"))

    for col in image_cols:
        name = url_to_basename(r.get(col))
        if not name: continue

        key = (title, color, code, col, name)
        if key in seen: continue
        seen.add(key)

        rows.append({
            "Title": title,
            "Colore": color,
            "ColorCode": code,
            "Brand": brand,
            "Stagione": season,
            "Type": typ,
            "image_col": col,
            "basename": name
        })

all_df = pd.DataFrame(rows)

files = existing_files()

# ================= FILTRI =================

st.subheader("Filtri")

search = st.text_input("Cerca titolo")

brands = st.multiselect("Brand", sorted(all_df["Brand"].unique()))
seasons = st.multiselect("Stagione", sorted(all_df["Stagione"].unique()))
colors = st.multiselect("Colore", sorted(all_df["Colore"].unique()))

filtered = all_df.copy()

if search:
    filtered = filtered[filtered["Title"].str.contains(search, case=False)]

if brands:
    filtered = filtered[filtered["Brand"].isin(brands)]

if seasons:
    filtered = filtered[filtered["Stagione"].isin(seasons)]

if colors:
    filtered = filtered[filtered["Colore"].isin(colors)]

titles = sorted(filtered["Title"].unique())
selected = st.selectbox("Prodotto", titles)

prod = filtered[filtered["Title"] == selected]

# ================= HEADER =================

codes = prod["ColorCode"].unique()
brand = ", ".join(prod["Brand"].unique())
season = ", ".join(prod["Stagione"].unique())

st.markdown(f"""
### {selected}
Brand: {brand}  
Stagione: {season}
""")

# ================= UI =================

for color in prod["Colore"].unique():

    sub = prod[prod["Colore"] == color]
    code = sub["ColorCode"].iloc[0]

    label = f"{color} ({code})" if code else color

    st.header(label)

    for _, r in sub.iterrows():

        name = r["basename"]

        st.subheader(f"{r['image_col']} {label}")

        c1, c2, c3 = st.columns([1,1,0.5])

        # upload
        with c1:
            up = st.file_uploader("Upload", key=name)
            if up:
                (out_dir / name).write_bytes(up.getbuffer())
                st.rerun()

        # preview
        with c2:
            if name in files:
                img = read_img(files[name])
                if img:
                    st.image(img)

        # delete
        with c3:
            if name in files:
                if st.button("🗑️", key="del_"+name):
                    delete_img(name)
                    st.rerun()

        st.divider()

st.success("Sistema pronto")
