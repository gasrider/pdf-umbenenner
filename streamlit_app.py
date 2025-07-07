import streamlit as st
import io
import re
import zipfile
from datetime import datetime

import fitz       # PyMuPDF
import pytesseract
from PIL import Image

import spacy

# ─── SpaCy-Setup ──────────────────────────────────────────────────────────────
# Modell "de_core_news_sm" wird via requirements.txt beim Build installiert
nlp = spacy.load("de_core_news_sm")


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
            ocr_text = pytesseract.image_to_string(img, lang="deu")
            full_text += ocr_text + "\n"
    doc.close()
    return full_text


# ─── Named-Entity-Recognition mittels SpaCy ──────────────────────────────────
def extract_name_ner(text: str) -> str | None:
    """
    Suche im gesamten Text nach ORG (Firmen) oder PER (Personen).
    """
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "ORG":
            return ent.text
    for ent in doc.ents:
        if ent.label_ == "PER":
            return ent.text
    return None


# ─── Heuristische Namenssuche als Fallback ───────────────────────────────────
def extract_name_fallback(text: str) -> str:
    """
    Fallback-Methoden:
    1) Zeile über Adresse
    2) Zeile mit 'Geb.datum'
    3) Erste fünf Zeilen auf Vorname Nachname prüfen
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    street_kw = ["straße", "strasse", "weg", "gasse", "platz", "allee"]

    # 1) Zeile direkt über einer Adresszeile
    for i, line in enumerate(lines):
        lw = line.lower()
        if any(kw in lw for kw in street_kw) and i > 0:
            cand = lines[i - 1]
            if 1 <= len(cand.split()) <= 4 and all(c.isalpha() or c.isspace() for c in cand):
                return cand

    # 2) Zeile mit "Geb.datum"
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


# ─── Hauptfunktion zur Namensextraktion ──────────────────────────────────────
def extract_customer_name(pdf_stream) -> str:
    """
    Kombiniere OCR, NER und Heuristiken.
    """
    text = extract_text_with_ocr(pdf_stream)

    # 0) NER-basiert
    name = extract_name_ner(text)
    if name:
        return name

    # 1–3) Fallback
    name = extract_name_fallback(text)
    if name:
        return name

    # 4) Letzter Ausweg
    return f"Unbekannt_{datetime.now().strftime('%Y%m%d%H%M%S')}"


# ─── Dateinamen bereinigen ───────────────────────────────────────────────────
def sanitize_filename(name: str) -> str:
    """
    Entferne Sonderzeichen und Leerzeichen für Dateinamen.
    """
    clean = re.sub(r"[^\w\s-]", "", name)
    return clean.replace(" ", "")


# ─── Streamlit-App ──────────────────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner mit OCR & NER", layout="centered")
st.title("📄 PDF-Umbenenner mit SpaCy-NER & OCR")

uploaded_files = st.file_uploader(
    "PDF-Dateien hochladen (max. 200 MB pro Datei)", 
    type="pdf", 
    accept_multiple_files=True
)

if uploaded_files:
    results = []
    errors = []

    with st.spinner("Verarbeite PDF-Dateien…"):
        for pdf_file in uploaded_files:
            pdf_file.seek(0)
            extracted_name = extract_customer_name(pdf_file)

            # Generiere finalen Dateinamen
            base = sanitize_filename(extracted_name)
            new_filename = f"Vertragsauskunft{base}.pdf"

            # Speichere Ergebnis
            pdf_file.seek(0)
            data = pdf_file.read()
            results.append((pdf_file.name, new_filename, data))

            if extracted_name.startswith("Unbekannt_"):
                errors.append(pdf_file.name)

    # Vorschau erkannter Dateinamen
    st.subheader("🔍 Vorschau erkannter Dateinamen")
    for orig, new, _ in results:
        st.write(f"• **{orig}** ➔ {new}")

    # ZIP-Archiv zum Download
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for _, new, data in results:
            zf.writestr(new, data)
    zip_buffer.seek(0)

    st.success("✅ Umbenennung abgeschlossen")
    st.download_button(
        label="📦 ZIP mit umbenannten PDFs herunterladen",
        data=zip_buffer,
        file_name="umbenannte_pdfs.zip",
        mime="application/zip"
    )

    if errors:
        st.warning("⚠️ Für diese Dateien konnte kein verlässlicher Name extrahiert werden:")
        for fn in errors:
            st.write(f"- {fn}")
