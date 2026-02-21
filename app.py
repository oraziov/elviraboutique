import io
import zipfile
import pandas as pd
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Assegna immagini per prodotto + colore", layout="wide")

def url_to_basename(x: str) -> str:
    """Converte URL/valore in basename file (es. .../abc.jpg?v=1 -> abc.jpg)."""
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
    return str(x).strip()

def sort_image_col(col: str) -> int:
    """Ordina Image1, Image2, Image3."""
    c = (col or "").lower().strip()
    if c.startswith("image"):
        try:
            return int(c.replace("image", ""))
        except:
            return 999
    return 999

st.title("Upload foto → rinomina con nomi dal CSV (Titolo + Colore + preview)")

csv_file = st.file_uploader("Carica il CSV", type=["csv"])
out_dir = Path("output_images")
out_dir.mkdir(exist_ok=True)

# ZIP download sempre disponibile
with st.sidebar:
    st.subheader("Download immagini assegnate")
    files = sorted([p for p in out_dir.glob("*") if p.is_file()])
    if files:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for p in files:
                z.write(p, arcname=p.name)
        buf.seek(0)
        st.download_button(
            label="⬇️ Scarica ZIP (output_images)",
            data=buf,
            file_name="output_images.zip",
            mime="application/zip",
        )
        st.caption(f"File nel ZIP: {len(files)}")
    else:
        st.info("Nessuna immagine salvata ancora.")

if csv_file:
    df = pd.read_csv(csv_file)

    image_cols = [c for c in ["Image1", "Image2", "Image3"] if c in df.columns]
    if not image_cols:
        st.error("Nel CSV non trovo Image1/Image2/Image3.")
        st.stop()

    if "Title" not in df.columns:
        st.error("Nel CSV non trovo la colonna 'Title'.")
        st.stop()

    # Colore può chiamarsi "Colore" (come nel tuo file). Se non esiste, usiamo vuoto.
    color_col = "Colore" if "Colore" in df.columns else None

    # Campi utili
    product_fields = [c for c in ["handle", "Title", "Type", "SKU", "Brand", "Colore"] if c in df.columns]

    # Costruisci righe uniche: (Title, Colore, ImageX, basename)
    rows = []
    seen = set()

    for _, row in df.iterrows():
        title = safe_str(row.get("Title", ""))
        if not title:
            continue

        color = safe_str(row.get(color_col, "")) if color_col else ""
        base_info = {k: safe_str(row.get(k, "")) for k in product_fields}

        for col in image_cols:
            raw = row.get(col, "")
            b = url_to_basename(raw)
            if not b:
                continue

            key = (title, color, col, b)
            if key in seen:
                continue
            seen.add(key)

            rec = {
                "Title": title,
                "Colore": color,
                "image_col": col,
                "basename": b,
                "image_url": "" if pd.isna(raw) else str(raw).strip(),
            }
            rec.update(base_info)
            rows.append(rec)

    if not rows:
        st.warning("Non ho trovato nomi immagini nelle colonne Image1/2/3.")
        st.stop()

    all_df = pd.DataFrame(rows)

    # Ordina: Title -> Colore -> Image1/2/3
    all_df["__img_order"] = all_df["image_col"].apply(sort_image_col)
    all_df = all_df.sort_values(
        by=["Title", "Colore", "__img_order", "basename"],
        ascending=[True, True, True, True]
    ).drop(columns=["__img_order"])

    # Lista titoli + filtro
    titles = sorted(all_df["Title"].dropna().unique().tolist())
    st.subheader("Filtra per Titolo prodotto")
    q = st.text_input("Cerca titolo (anche parziale)", value="")
    filtered_titles = [t for t in titles if q.lower() in t.lower()] if q else titles

    if not filtered_titles:
        st.warning("Nessun titolo corrisponde al filtro.")
        st.stop()

    selected_title = st.selectbox("Seleziona Titolo", filtered_titles, index=0)
    prod_df = all_df[all_df["Title"] == selected_title].copy()

    # File già salvati
    existing_files = {p.name: p for p in out_dir.glob("*")}

    # Meta prodotto (dalla prima riga)
    first = prod_df.iloc[0].to_dict()
    meta_keys = ["Brand", "Type", "handle"]
    meta = {k: first.get(k, "") for k in meta_keys if first.get(k, "")}
    if meta:
        st.write(meta)

    # Colori disponibili per questo titolo
    colors = prod_df["Colore"].fillna("").unique().tolist()
    # metti "SENZA COLORE" come label se vuoto
    colors_sorted = sorted(colors, key=lambda x: (x == "", x))

    # Layout
    colL, colR = st.columns([3, 2])

    with colL:
        st.subheader("Prodotto selezionato → immagini per colore (in ordine Image1 → Image3)")

        for color in colors_sorted:
            color_label = color if color else "SENZA COLORE"
            st.markdown(f"## 🎨 Colore: **{color_label}**")

            sub = prod_df[prod_df["Colore"].fillna("") == (color or "")].copy()

            # Galleria da CSV per quel colore
            st.markdown("**Galleria (da CSV)**")
            urls = [u for u in sub["image_url"].tolist() if isinstance(u, str) and u.strip()]
            if urls:
                st.image(urls[:3], use_container_width=True)
            else:
                st.info("Nessun URL nel CSV per questo colore.")

            # Righe Image1/2/3
            for _, r in sub.reset_index(drop=True).iterrows():
                basename = r["basename"]
                img_col = r["image_col"]
                image_url = r.get("image_url", "")

                st.markdown(f"### {img_col}  •  `{basename}`")

                c1, c2, c3, c4 = st.columns([2, 2, 2, 2])

                with c1:
                    up = st.file_uploader(
                        f"Carica file per {img_col} ({color_label})",
                        type=["jpg", "jpeg", "png", "webp"],
                        key=f"upl_{selected_title}_{color_label}_{img_col}_{basename}",
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
                    st.markdown("**Info:**")
                    st.write({
                        "Title": r.get("Title", ""),
                        "Colore": color_label,
                        "handle": r.get("handle", ""),
                        "Type": r.get("Type", ""),
                    })

                st.divider()

    with colR:
        st.subheader("Stato (Titolo selezionato)")

        # stato assegnazione per righe del titolo
        prod_df["assegnata"] = prod_df["basename"].apply(
            lambda x: x in existing_files and existing_files[x].exists()
        )

        # riepilogo per colore
        summary = (
            prod_df.groupby("Colore", dropna=False)["assegnata"]
            .agg(totale="count", assegnate="sum")
            .reset_index()
        )
        summary["Colore"] = summary["Colore"].apply(lambda x: x if x else "SENZA COLORE")
        st.dataframe(summary, use_container_width=True, hide_index=True)

        # mancanti del titolo
        missing = prod_df[~prod_df["assegnata"]][["Colore", "image_col", "basename"]].copy()
        missing["Colore"] = missing["Colore"].apply(lambda x: x if x else "SENZA COLORE")

        if len(missing):
            st.warning(f"Mancano {len(missing)} immagini per questo Titolo.")
            st.dataframe(
                missing.rename(columns={"image_col": "colonna"}),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.success("Questo Titolo è completo ✅")

        st.subheader("Stato totale (tutti i prodotti)")
        total_needed = len(all_df)
        total_done = sum(
            (b in existing_files and existing_files[b].exists())
            for b in all_df["basename"].tolist()
        )
        st.metric("Immagini assegnate", f"{total_done} / {total_needed}")

        only_missing = st.checkbox("Mostra solo mancanti (globale)", value=True)
        global_df = all_df.copy()
        global_df["assegnata"] = global_df["basename"].apply(
            lambda x: x in existing_files and existing_files[x].exists()
        )
        if only_missing:
            global_df = global_df[~global_df["assegnata"]]

        # Mostra globale ordinato per Title->Colore->Image
        global_df_view = global_df[["Title", "Colore", "image_col", "basename", "assegnata"]].copy()
        global_df_view["Colore"] = global_df_view["Colore"].apply(lambda x: x if x else "SENZA COLORE")
        global_df_view = global_df_view.rename(columns={"image_col": "colonna"})

        st.dataframe(global_df_view, use_container_width=True, hide_index=True)

else:
    st.info("Carica un CSV per iniziare.")
