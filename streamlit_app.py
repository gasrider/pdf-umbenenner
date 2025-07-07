import streamlit as st
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import re
import zipfile
from datetime import datetime
import spacy
from spacy.cli import download as spacy_download

# Load SpaCy model, download if missing
try:
    nlp = spacy.load("de_core_news_sm")
except OSError:
    spacy_download("de_core_news_sm")
    nlp = spacy.load("de_core_news_sm")

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

def extract_name_ner(text):
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "ORG":
            return ent.text
    for ent in doc.ents:
        if ent.label_ == "PER":
            return ent.text
    return None

def extract_customer_name(text):
    name = extract_name_ner(text)
    if name:
        return name
    lines = text.splitlines()
    street_kw = ["straße", "strasse", "weg", "gasse", "platz", "allee"]
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in street_kw) and i>0:
            cand = lines[i-1].strip()
            if 1<=len(cand.split())<=4 and all(c.isalpha() or c.isspace() for c in cand):
                return cand
    for line in lines:
        if "geb.datum" in line.lower():
            parts = line.split("Geb.datum")[0].strip()
            if len(parts.split())>=2:
                return parts
    for line in lines[:5]:
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+", line.strip()):
            return line.strip()
    return "Kein_Name_Gefunden"

def sanitize_filename(name):
    clean = re.sub(r"[^\w\s-]", "", name)
    return clean.replace(" ", "")

st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("PDF-Umbenenner mit OCR & NER")

files = st.file_uploader("PDF-Dateien hochladen", type="pdf", accept_multiple_files=True)
if files:
    entries, errors = [], []
    with st.spinner("Verarbeite..."):
        for f in files:
            f.seek(0)
            text = extract_text_with_ocr(f)
            cust = extract_customer_name(text)
            if not cust or cust=="Kein_Name_Gefunden":
                cust = f"Unbekannt_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                errors.append(f.name)
            safe = sanitize_filename(cust)
            new = f"Vertragsauskunft{safe}.pdf"
            f.seek(0)
            data = f.read()
            entries.append((new, data))
    st.subheader("Erkannte Dateien")
    for orig, (new, _) in zip([f.name for f in files], entries):
        st.write(f"{orig} ➔ {new}")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for new, data in entries:
            z.writestr(new, data)
    buf.seek(0)
    st.download_button("ZIP herunterladen", buf, "umbenannte_pdfs.zip", "application/zip")
    if errors:
        st.warning("Fehler bei: " + ", ".join(errors))
