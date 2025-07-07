import streamlit as st
import io
import re
import zipfile
from datetime import datetime

import fitz       # PyMuPDF
import pytesseract
from PIL import Image

# ─── Textextraktion mit OCR-Fallback ──────────────────────────────────────────
def extract_text_with_ocr(pdf_stream) -> str:
    """
    Versuche erst PDF-Text, sonst OCR via Tesseract.
    """
    doc = fitz.open(stream=pdf_stream.read(), filetype="pdf")
    full_text = ""
    for page in doc:
        block = page.get_text().strip()
        if block:
            full_text += block + "\n"
        else:
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            full_text += pytesseract.image_to_string(img, lang="deu") + "\n"
    doc.close()
    return full_text

# ─── Heuristische Namenssuche ─────────────────────────────────────────────────
def extract_customer_name(text: str) -> str:
    """
    1) Zeile über einer Adresszeile
    2) Zeile mit 'Geb.datum'
    3) Erste fünf Zeilen mit 'Vorname Nachname'
    4) Fallback: Zeitstempel-Unbekanntsname
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    street_kw = ["straße","strasse","weg","gasse","platz","allee"]

    # 1) Name über Adresse
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in street_kw) and i > 0:
            cand = lines[i-1]
            if 1 <= len(cand.split()) <= 4 and all(c.isalpha() or c.isspace() for c in cand):
                return cand

    # 2) Zeile mit Geburtsdatum
    for line in lines:
        if "geb.datum" in line.lower():
            p = line.split("Geb.datum")[0].strip()
            if len(p.split()) >= 2:
                return p

    # 3) Erste 5 Zeilen: Vorname Nachname
    for line in lines[:5]:
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+", line):
            return line

    # 4) Fallback
    return f"Unbekannt_{datetime.now():%Y%m%d%H%M%S}"

# ─── Dateinamen bereinigen ────────────────────────────────────────────────────
def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w]", "", name)

# ─── Streamlit-App ──────────────────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner (OCR + Heuristiken)")

uploaded = st.file_uploader(
    "PDF-Dateien hochladen (max. 200 MB/Datei)", 
    type="pdf", 
    accept_multiple_files=True
)

if uploaded:
    results, errors = [], []
    with st.spinner("Verarbeitung läuft…"):
        for pdf in uploaded:
            pdf.seek(0)
            txt = extract_text_with_ocr(pdf)
            name = extract_customer_name(txt)
            if name.startswith("Unbekannt_"):
                errors.append(pdf.name)
            safe = sanitize_filename(name)
            new_fn = f"Vertragsauskunft{safe}.pdf"
            pdf.seek(0)
            data = pdf.read()
            results.append((pdf.name, new_fn, data))

    # Vorschau
    st.subheader("🔍 Vorschau der neuen Dateinamen")
    for orig, new, _ in results:
        st.write(f"• **{orig}** ➔ {new}")

    # ZIP erstellen
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for _, new, data in results:
            zf.writestr(new, data)
    buf.seek(0)

    st.download_button(
        "📦 ZIP mit umbenannten PDFs herunterladen",
        buf,
        file_name="umbenannte_pdfs.zip",
        mime="application/zip"
    )

    if errors:
        st.warning("⚠️ Bei diesen Dateien kein Name gefunden:")
        for e in errors:
            st.write(f"- {e}")
