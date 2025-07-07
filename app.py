import streamlit as st
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import re
import zipfile
from datetime import datetime

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

def extract_customer_name(text):
    lines = text.splitlines()
    street_keywords = ["straße", "strasse", "weg", "gasse", "platz", "allee"]
    blacklist_keywords = [
        "versicherung", "vertragsauskunft", "beginn", "ablauf", "ag", "gmbh",
        "versicherungsverein", "datum", "geburtsdatum", "kundennummer"
    ]

    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in street_keywords) and i > 0:
            candidate = lines[i - 1].strip()
            if (1 <= len(candidate.split()) <= 4 and
                all(c.isalpha() or c.isspace() for c in candidate)):
                return candidate

    for line in lines:
        if "geb.datum" in line.lower():
            parts = line.split("Geb.datum")[0].strip()
            if len(parts.split()) >= 2:
                return parts

    for line in lines[:5]:
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+", line.strip()):
            return line.strip()

    return "Kein_Name_Gefunden"

def sanitize_filename(name):
    name = re.sub(r"[^\w\s-]", "", name)
    return name.replace(" ", "")

st.title("PDF-Umbenenner mit OCR-Unterstützung")
uploaded_files = st.file_uploader("PDF-Dateien hochladen", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    renamed = []
    errors = []
    with st.spinner("Verarbeite Dateien..."):
        for uploaded_file in uploaded_files:
            uploaded_file.seek(0)
            text = extract_text_with_ocr(uploaded_file)
            name = extract_customer_name(text)
            if not name or name == "Kein_Name_Gefunden":
                name = f"Unbekannt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                errors.append(uploaded_file.name)
            filename = f"Vertragsauskunft{name.replace(' ', '')}.pdf"
            uploaded_file.seek(0)
            file_bytes = uploaded_file.read()
            renamed.append((filename, file_bytes))

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for filename, filedata in renamed:
            zipf.writestr(filename, filedata)
    zip_buffer.seek(0)

    st.success("Verarbeitung abgeschlossen!")
    st.download_button(
        label="ZIP herunterladen mit umbenannten PDFs",
        data=zip_buffer,
        file_name="umbenannte_pdfs.zip",
        mime="application/zip",
    )

    st.subheader("Erkannte Kundennamen:")
    for filename, _ in renamed:
        st.write(filename)

    if errors:
        st.warning("⚠️ Bei folgenden Dateien konnte kein Name erkannt werden:")
        for e in errors:
            st.write(e)
