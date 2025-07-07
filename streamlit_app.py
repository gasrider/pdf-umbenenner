import streamlit as st
import io
import re
import zipfile
from datetime import datetime

import fitz       # PyMuPDF
import pytesseract
from PIL import Image

# ─── OCR / Textextraktion ────────────────────────────────────────────────────
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

# ─── Bounding-Box Name-Detection mit Header-Blacklist ─────────────────────────
def extract_name_by_bbox(pdf_stream) -> str | None:
    """
    Durchsuche den oberen Bereich (10–30% Höhe) nach Namen, 
    überspringe bekannte Header-Begriffe.
    """
    pdf_stream.seek(0)
    doc = fitz.open(stream=pdf_stream.read(), filetype="pdf")
    page = doc[0]
    height = page.rect.height
    blocks = page.get_text("dict")["blocks"]

    y_min, y_max = height * 0.10, height * 0.30

    # Header-Blacklist (kleingeschrieben)
    blacklist = [
        "mondsee", "finanz", "rainerstraße", "a-5310", "5310", "gmbh", "kundevertragsspiegel"
    ]

    candidates = []
    for block in blocks:
        y0 = block["bbox"][1]
        if not (y_min < y0 < y_max):
            continue

        # Block-Text zusammenführen
        text = " ".join(
            span["text"] 
            for line in block["lines"] 
            for span in line["spans"]
        ).strip()

        low = text.lower()
        if any(hw in low for hw in blacklist):
            continue

        # Mehrfach-Whitespace bereinigen
        text = re.sub(r"\s+", " ", text)

        # Muster: Person (2–5 Wörter, Großbuchstaben) oder Firma (endet auf GmbH)
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+(?: [A-ZÄÖÜ][a-zäöüß]+){1,4}$", text) \
        or re.match(r"^[A-ZÄÖÜ].*GmbH$", text):
            candidates.append(text)

    doc.close()
    return candidates[0] if candidates else None

# ─── Heuristische Fallbacks ─────────────────────────────────────────────────
def extract_name_fallback(text: str) -> str | None:
    """
    1) Name über einer Adresszeile
    2) Zeile mit 'Geb.datum'
    3) Erste 5 Zeilen nach Vorname Nachname
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    street_kw = ["straße","strasse","weg","gasse","platz","allee"]

    # 1) Zeile über Adresse
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in street_kw) and i > 0:
            cand = lines[i-1]
            if 1 <= len(cand.split()) <= 4 and all(c.isalpha() or c.isspace() for c in cand):
                return cand

    # 2) Zeile mit Geburtsdatum
    for line in lines:
        if "geb.datum" in line.lower():
            parts = line.split("Geb.datum")[0].strip()
            if len(parts.split()) >= 2:
                return parts

    # 3) Erste fünf Zeilen: Vorname Nachname
    for line in lines[:5]:
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+", line):
            return line

    return None

# ─── Gesamt-Extraktion ──────────────────────────────────────────────────────
def extract_customer_name(pdf_stream) -> str:
    # 1) Bounding-Box-Methode
    name = extract_name_by_bbox(pdf_stream)
    if name:
        return name

    # 2) OCR + Fallback
    pdf_stream.seek(0)
    text = extract_text_with_ocr(pdf_stream)
    name = extract_name_fallback(text)
    if name:
        return name

    # 3) Letzter Ausweg
    return f"Unbekannt_{datetime.now():%Y%m%d%H%M%S}"

# ─── Dateinamen sanitisieren ──────────────────────────────────────────────────
def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w]", "", name)

# ─── Streamlit UI ───────────────────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner mit OCR & Koordinaten-Heuristik")

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
            cust = extract_customer_name(pdf)
            if cust.startswith("Unbekannt_"):
                errors.append(pdf.name)
            safe = sanitize_filename(cust)
            new_name = f"Vertragsauskunft{safe}.pdf"
            pdf.seek(0)
            data = pdf.read()
            results.append((pdf.name, new_name, data))

    # Vorschau
    st.subheader("🔍 Vorschau der neuen Dateinamen")
    for orig, new, _ in results:
        st.write(f"• **{orig}** ➔ {new}")

    # ZIP
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for _, new, data in results:
            zf.writestr(new, data)
    buf.seek(0)

    st.download_button(
        "📦 ZIP herunterladen",
        buf,
        file_name="umbenannte_pdfs.zip",
        mime="application/zip"
    )

    if errors:
        st.warning("⚠️ Diese Dateien konnten nicht automatisch benannt werden:")
        for e in errors:
            st.write(f"- {e}")
