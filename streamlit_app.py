import streamlit as st
import fitz    # PyMuPDF
import io
import re
import zipfile
from datetime import datetime

# ─── 1) PDFs lesen und Blöcke sortieren ───────────────────────────────────────
def get_sorted_blocks(pdf_bytes: bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    blocks = []
    for blk in page.get_text("dict")["blocks"]:
        # Block-Koordinaten, ganzer Block-Text
        x0, y0, x1, y1 = blk["bbox"]
        text = " ".join(
            span["text"] for line in blk["lines"] for span in line["spans"]
        ).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            blocks.append((y0, text))
    doc.close()
    # Nach oberer Y-Koordinate sortieren (vom oberen Rand nach unten)
    return sorted(blocks, key=lambda t: t[0])

# ─── 2) Kundenname extrahieren über Adress-Block-Position ────────────────────
def extract_name_via_address(pdf_bytes: bytes) -> str | None:
    blocks = get_sorted_blocks(pdf_bytes)
    street_kw = ["straße","strasse","weg","gasse","platz","allee"]
    # Suche nach dem ersten Block, der eine Straße enthält
    for idx, (_, text) in enumerate(blocks):
        low = text.lower()
        if any(kw in low for kw in street_kw):
            # Kandidat direkt davor
            if idx > 0:
                cand = blocks[idx-1][1]
                # Nur Buchstaben und Leerzeichen
                if re.match(r"^[A-Za-zÄÖÜäöüß .°\-/]+$", cand):
                    return cand
    return None

# ─── 3) Heuristischer Fallback über Gesamttext ───────────────────────────────
def extract_name_fallback(full_text: str) -> str | None:
    lines = [l.strip() for l in full_text.splitlines() if l.strip()]
    # a) Vor 'Geb.datum'
    for line in lines:
        if "geb.datum" in line.lower():
            cand = line.split("geb.datum")[0].strip()
            if re.match(r"^[A-Za-zÄÖÜäöüß ]+$", cand):
                return cand
    # b) Erste 5 Zeilen 'Vorname Nachname'
    for line in lines[:5]:
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+", line):
            return line
    return None

# ─── 4) Vollständige Extraktion ─────────────────────────────────────────────
def extract_customer_name(pdf_bytes: bytes) -> str:
    # per Block-Position
    name = extract_name_via_address(pdf_bytes)
    if name:
        return name

    # gesamter Text als Fallback
    doc_text = get_sorted_blocks(pdf_bytes)
    full = "\n".join(t for _, t in doc_text)
    fb = extract_name_fallback(full)
    if fb:
        return fb

    # falls gar nichts passt
    return f"Unbekannt_{datetime.now():%Y%m%d%H%M%S}"

# ─── 5) Dateiname sanitisieren ───────────────────────────────────────────────
def sanitize_filename(name: str) -> str:
    # Sonderzeichen entfernen, Leerzeichen behalten
    return re.sub(r"[^\w\s]", "", name).strip()

# ─── 6) Streamlit UI ─────────────────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner (Name über Adresse)")

uploads = st.file_uploader(
    "PDF-Dateien hochladen (max. 200 MB/pro Datei)",
    type="pdf",
    accept_multiple_files=True
)

if uploads:
    results, errors = [], []
    for f in uploads:
        data = f.read()
        cust = extract_customer_name(data)
        if cust.startswith("Unbekannt_"):
            errors.append(f.name)
        safe = sanitize_filename(cust)
        new_fn = f"Vertragsauskunft {safe}.pdf"
        results.append((f.name, new_fn, data))

    st.subheader("🔍 Vorschau der neuen Dateinamen")
    for orig, new, _ in results:
        st.write(f"• **{orig}** ➔ {new}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for _, new, pdf_data in results:
            zf.writestr(new, pdf_data)
    buf.seek(0)

    st.download_button(
        "📦 ZIP herunterladen mit umbenannten PDFs",
        buf,
        file_name="umbenannte_pdfs.zip",
        mime="application/zip"
    )

    if errors:
        st.warning("⚠️ Kein Name gefunden in:")
        for e in errors:
            st.write(f"- {e}")
