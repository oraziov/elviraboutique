import os
import pandas as pd
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Assegna immagini (filtra per Titolo + preview CSV)", layout="wide")

def url_to_basename(x: str) -> str:
    """Converte un URL/valore in basename file (es. .../abc.jpg?v=1 -> abc.jpg)."""
    if pd.isna(x):
        return ""
    s = str(x).strip()
    if not s or s.lower() == "nan":
        return ""
    s = s.split("?")[0]
    return s.rsplit("/", 1)[-1]

def safe_str(x) -> str:
    if pd.isna(x):
        return ""
    return str(x)

def sort_image_col(col: str) -> int:
    """Ordina Image1, Image2, Image3."""
    c = (col or "").lower().strip()
    if c.startswith("image"):
        try:
            return int(c.replace("image", ""))
        except:
            return 999
    return 999

st.title("Upload foto → rinomina con nomi dal CSV (filtra per Titolo + anteprima CSV e caricata)")

csv_file = st.file_uploader("Carica il CSV", type=["csv"])
out_dir = Path("output_images")
out_dir.mkdir(exist_ok=True)

if csv_file:
    df = pd.read_csv(csv_file)

    image_cols = [c for c in ["Image1", "Image2", "Image3"] if c in df.columns]
    if not image_cols:
        st.error("Nel CSV non trovo Image1/Image2/Image3.")
        st.stop()

    if "Title" not in df.columns:
        st.error("Nel CSV non trovo la colonna 'Title'.")
        st.stop()

    # Campi prodotto utili (se presenti)
    product_fields = [c for c in ["handle", "Title", "Type", "SKU", "Brand", "Colore"] if c in df.columns]

    # Costruisci record immagine richieste (per prodotto + posizione Image1/2/3)
    # Ogni record: Title, image_col, basename, image_url + meta prodotto
    rows = []
    seen = set()  # evita duplicati (Title, image_col, basename)

    for _, row in df.iterrows():
        title = safe_str(row.get("Title", "")).strip()
        if not title:
            continue

        base_info = {k: safe_str(row.get(k, "")).strip() for k in product_fields}

        for col in image_cols:
            raw = row.get(col, "")
            b = url_to_basename(raw)
            if not b:
                continue

            key = (title, col, b)
            if key in seen:
                continue
            seen.add(key)

            rec = {
                "Title": title,
                "image_col": col,
                "basename": b,
                "image_url": "" if pd.isna(raw) else str(raw).strip(),  # <-- URL originale dal CSV
            }
            rec.update(base_info)
            rows.append(rec)

    if not rows:
        st.warning("Non ho trovato nomi immagini nelle colonne Image1/2/3.")
        st.stop()

    all_df = pd.DataFrame(rows)

    # Ordina per prodotto (Title), poi Image1->Image2->Image3, poi basename
    all_df["__img_order"] = all_df["image_col"].apply(sort_image_col)
    all_df = all_df.sort_values(by=["Title", "__img_order", "basename"], ascending=[True, True, True]).drop(columns=["__img_order"])

    # Prepara lista titoli + filtro
    titles = sorted(all_df["Title"].dropna().unique().tolist())

    st.subheader("Filtra per Titolo prodotto")
    q = st.text_input("Cerca titolo (anche parziale)", value="")

    filtered_titles = [t for t in titles if q.lower() in t.lower()] if q else titles
    if not filtered_titles:
        st.warning("Nessun titolo corrisponde al filtro.")
        st.stop()

    selected_title = st.selectbox("Seleziona Titolo", filtered_titles, index=0)

    # Dataset prodotto selezionato
    prod_df = all_df[all_df["Title"] == selected_title].copy()

    # Stato: file già creati in output_images
    existing_files = {p.name: p for p in out_dir.glob("*")}

    # Layout
    colL, colR = st.columns([3, 2])

    with colL:
        st.subheader("Immagini del prodotto (ordine Image1 → Image2 → Image3)")

        # Meta prodotto (dalla prima riga)
        first = prod_df.iloc[0].to_dict()
        meta_keys = ["Brand", "Type", "Colore", "handle", "SKU"]
        meta = {k: first.get(k, "") for k in meta_keys if first.get(k, "")}
        if meta:
            st.write(meta)

        # Galleria prodotto dal CSV (URL)
        st.markdown("### Galleria prodotto (da CSV)")
        urls = [u for u in prod_df["image_url"].tolist() if isinstance(u, str) and u.strip()]
        if urls:
            st.image(urls[:3], use_container_width=True)
        else:
            st.info("Nessuna immagine nel CSV per questo prodotto.")

        st.caption("Per ogni riga carica la foto: verrà salvata con il basename esatto. Vedi anche anteprima da CSV e anteprima salvata.")

        # Righe per Image1/2/3
        for _, r in prod_df.reset_index(drop=True).iterrows():
            basename = r["basename"]
            img_col = r["image_col"]
            image_url = r.get("image_url", "")

            st.markdown(f"### {img_col}  •  `{basename}`")

            c1, c2, c3, c4 = st.columns([2, 2, 2, 2])

            with c1:
                up = st.file_uploader(
                    f"Carica file per {img_col}",
                    type=["jpg", "jpeg", "png", "webp"],
                    key=f"u_{selected_title}_{img_col}_{basename}",
                )
                if up is not None:
                    (out_dir / basename).write_bytes(up.getbuffer())
                    st.success(f"Salvato come: {basename}")
                    existing_files[basename] = (out_dir / basename)

            with c2:
                st.markdown("**Anteprima (da CSV):**")
                if isinstance(image_url, str) and image_url.strip():
                    st.image(image_url, use_container_width=True)
                else:
                    st.info("Nessun URL nel CSV.")

            with c3:
                st.markdown("**Anteprima (caricata):**")
                p = existing_files.get(basename)
                if p and p.exists():
                    st.image(str(p), use_container_width=True)
                else:
                    st.info("Non ancora assegnata.")

            with c4:
                st.markdown("**Info prodotto:**")
                st.write({
                    "Title": r.get("Title", ""),
                    "Type": r.get("Type", ""),
                    "handle": r.get("handle", ""),
                })

            st.divider()

    with colR:
        st.subheader("Stato prodotto selezionato")

        prod_df["assegnata"] = prod_df["basename"].apply(lambda x: x in existing_files and existing_files[x].exists())
        st.dataframe(
            prod_df[["image_col", "basename", "assegnata"]].rename(columns={"image_col": "colonna"}),
            use_container_width=True,
            hide_index=True
        )

        missing = prod_df[~prod_df["assegnata"]]["basename"].tolist()
        if missing:
            st.warning(f"Mancano {len(missing)} immagini per questo prodotto.")
            st.write(missing)
        else:
            st.success("Questo prodotto è completo ✅")

        st.subheader("Stato totale (tutti i prodotti)")
        total_needed = len(all_df)
        total_done = sum((b in existing_files and existing_files[b].exists()) for b in all_df["basename"].tolist())
        st.metric("Immagini assegnate", f"{total_done} / {total_needed}")

        only_missing = st.checkbox("Mostra solo mancanti (globale)", value=True)

        global_df = all_df.copy()
        global_df["assegnata"] = global_df["basename"].apply(lambda x: x in existing_files and existing_files[x].exists())
        if only_missing:
            global_df = global_df[~global_df["assegnata"]]

        st.dataframe(
            global_df[["Title", "image_col", "basename", "assegnata"]].rename(columns={"image_col": "colonna"}),
            use_container_width=True,
            hide_index=True
        )
else:
    st.info("Carica un CSV per iniziare.")
