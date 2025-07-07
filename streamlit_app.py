import streamlit as st
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import re
import zipfile
from datetime import datetime

# --- Texterkennung mit OCR (Fallback) ---
def extract_text_with_ocr(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    full_text = ""
    for page in doc:
        text = page.get_text()
        if text.strip():
            full_text += text + "\n"
        else:
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            ocr_text = pytesseract.image_to_string(img, lang='deu')
            full_text += ocr_text + "\n"
    return full_text

# --- Kundennamen extrahieren ---
def extract_customer_name(text):
    lines = text.splitlines()
    street_keywords = ["straße", "strasse", "weg", "gasse", "platz", "allee"]
    blacklist_keywords = [
        "versicherung", "vertragsauskunft", "beginn", "ablauf", "ag", "gmbh",
        "versicherungsverein", "datum", "geburtsdatum", "kundennummer"
    ]

    # 1) Zeile über Adresse
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in street_keywords) and i > 0:
            candidate = lines[i - 1].strip()
            if 1 <= len(candidate.split()) <= 4 and all(c.isalpha() or c.isspace() for c in candidate):
                return candidate

    # 2) Zeile mit "Geb.datum"
    for line in lines:
        if "geb.datum" in line.lower():
            parts = line.split("Geb.datum")[0].strip()
            if len(parts.split()) >= 2:
                return parts

    # 3) Fallback: Erste 5 Zeilen nach Vorname Nachname
    for line in lines[:5]:
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+", line.strip()):
            return line.strip()

    return "Kein_Name_Gefunden"

# --- Dateinamen sanitisieren ---
def sanitize_filename(name: str) -> str:
    clean = re.sub(r"[^\w\s-]", "", name)
    return clean.replace(" ", "")

# --- Streams of App ---
st.set_page_config(page_title="PDF-Umbenenner mit OCR & Korrektur", layout="centered")
st.title("📄 PDF-Umbenenner mit OCR & manueller Korrektur")

uploaded_files = st.file_uploader("PDF-Dateien hochladen", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    # Zwischenspeicher für erkannte Dateien
    recognized = []
    errors = []

    with st.spinner("Verarbeitung läuft..."):
        for uploaded_file in uploaded_files:
            uploaded_file.seek(0)
            text = extract_text_with_ocr(uploaded_file)
            name = extract_customer_name(text)
            if not name or name == "Kein_Name_Gefunden":
                name = f"Unbekannt_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                errors.append(uploaded_file.name)

            base = sanitize_filename(name)
            new_filename = f"Vertragsauskunft{base}.pdf"

            # Zurücksetzen und Buffer lesen
            uploaded_file.seek(0)
            data = uploaded_file.read()
            recognized.append({
                "orig": uploaded_file.name,
                "suggested": new_filename,
                "data": data
            })

    # Vorschau der erkannten Namen
    st.subheader("🔍 Vorschau erkannter Namen")
    for item in recognized:
        st.write(f"• **{item['orig']}** ➔ {item['suggested']}")

    # Manueller Korrekturbereich
    st.subheader("✏️ Korrigiere bei Bedarf")
    corrected = []
    for item in recognized:
        default = item["suggested"].replace("Vertragsauskunft", "").replace(".pdf", "")
        user_input = st.text_input(
            label=f"Name für {item['orig']}",
            value=default,
            key=item["orig"]
        ).strip()
        clean = sanitize_filename(user_input)
        final_name = f"Vertragsauskunft{clean}.pdf"
        corrected.append({
            "filename": final_name,
            "data": item["data"]
        })

    # ZIP-Erstellung mit korrigierten Namen
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for item in corrected:
            zipf.writestr(item["filename"], item["data"])
    zip_buffer.seek(0)

    st.success("✅ Fertig! Hier ist dein Download:")
    st.download_button(
        label="📦 ZIP mit umbenannten PDFs herunterladen",
        data=zip_buffer,
        file_name="umbenannte_pdfs_final.zip",
        mime="application/zip"
    )

    # Fehlermeldungen anzeigen
    if errors:
        st.warning("⚠️ Für diese Dateien wurde kein Name automatisch erkannt:")
        for e in errors:
            st.write(f"- {e}")
