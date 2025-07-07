import streamlit as st
import fitz  # PyMuPDF
import os
import io
import zipfile
import re
from datetime import datetime

st.set_page_config(page_title="PDF-Umbenenner nach Kundennamen", layout="centered")
st.title("📄 PDF-Umbenenner nach Kundennamen")

# Funktion: Text aus PDF extrahieren
def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# Funktion: Kundennamen erkennen
def extract_customer_name(text):
    lines = text.splitlines()
    street_keywords = ["straße", "strasse", "weg", "gasse", "platz", "allee"]
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(kw in line_lower for kw in street_keywords):
            if i > 0:
                candidate = lines[i - 1].strip()
                if 1 <= len(candidate.split()) <= 4 and re.search(r"[A-Za-z]", candidate):
                    return candidate

    # Fallback: Suche nach Zeile mit "Geb.datum"
    for line in lines:
        if "geb.datum" in line.lower():
            match = re.split(r"[Gg]eb\.datum", line)
            if len(match) > 0:
                possible_name = match[0].strip()
                name_parts = possible_name.split()
                if 1 <= len(name_parts) <= 4:
                    return possible_name

    return "Kein_Name_Gefunden"

# Funktion: PDF-Dateien umbenennen und zippen
def rename_and_zip_pdfs(uploaded_files):
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zip_file:
        for uploaded_file in uploaded_files:
            text = extract_text_from_pdf(uploaded_file)
            name = extract_customer_name(text)

            # Formatieren des Namens
            name = re.sub(r"[^\w\s]", "", name)  # Sonderzeichen entfernen
            name = name.replace(" ", "")  # Leerzeichen entfernen

            new_filename = f"{name}.pdf"
            zip_file.writestr(new_filename, uploaded_file.getvalue())

    zip_buffer.seek(0)
    return zip_buffer

# Upload
uploaded_files = st.file_uploader("🔼 Lade eine oder mehrere PDF-Dateien hoch", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    # Vorschau anzeigen (Name + Seiteninhalt)
    with st.expander("📋 Vorschau der erkannten Namen (Klick zum Öffnen)"):
        for file in uploaded_files:
            text = extract_text_from_pdf(file)
            name = extract_customer_name(text)
            st.markdown(f"**{file.name} ➜ {name}**")

    if st.button("📥 Umbenennen & ZIP-Datei herunterladen"):
        zip_file = rename_and_zip_pdfs(uploaded_files)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        st.download_button(
            label="📦 Download ZIP",
            data=zip_file,
            file_name=f"umbenannte_pdfs_{timestamp}.zip",
            mime="application/zip"
        )
