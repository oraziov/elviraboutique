import pandas as pd
import streamlit as st

st.set_page_config(page_title="Color Viewer", layout="wide")

st.title("Gestione colori prodotti")

# =====================================================
# UPLOAD CSV
# =====================================================

csv_file = st.file_uploader("Carica CSV", type=["csv"])

if not csv_file:
    st.stop()

df = pd.read_csv(csv_file)

# =====================================================
# CONTROLLI
# =====================================================

if "Title" not in df.columns:
    st.error("Colonna Title mancante")
    st.stop()

if "Colore" not in df.columns:
    st.error("Colonna Colore mancante")
    st.stop()

if "color_code" not in df.columns:
    st.error("Colonna color_code mancante")
    st.stop()

# =====================================================
# PULIZIA DATI
# =====================================================

def clean(x):
    if pd.isna(x):
        return ""
    return str(x).strip()

df["Title"] = df["Title"].apply(clean)
df["Colore"] = df["Colore"].apply(clean)
df["color_code"] = df["color_code"].apply(clean)

# rimuove duplicati
df = df.drop_duplicates(subset=["Title", "Colore", "color_code"])

# =====================================================
# FILTRO COLOR CODE
# =====================================================

color_codes = sorted([c for c in df["color_code"].unique() if c])

selected_code = st.selectbox(
    "Filtra per Color Code",
    ["Tutti"] + color_codes
)

filtered_df = df.copy()

if selected_code != "Tutti":
    filtered_df = filtered_df[
        filtered_df["color_code"] == selected_code
    ]

# =====================================================
# SELEZIONE TITOLO
# =====================================================

titles = sorted(filtered_df["Title"].unique())

if not titles:
    st.warning("Nessun risultato")
    st.stop()

selected_title = st.selectbox("Seleziona prodotto", titles)

prod_df = filtered_df[filtered_df["Title"] == selected_title]

# =====================================================
# OUTPUT
# =====================================================

st.subheader("Colori disponibili")

for _, row in prod_df.iterrows():
    colore = row["Colore"] or "SENZA NOME"
    codice = row["color_code"]

    st.write(f"🎨 {colore}  |  Codice: {codice}")
