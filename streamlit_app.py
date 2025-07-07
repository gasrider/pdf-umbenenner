
import streamlit as st
import fitz  # PyMuPDF
import re
import zipfile
import os

def extract_customer_name(text):
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if any(word.lower() in line.lower() for word in ["gmbh", "versicherung", "uniqa", "polizze", "vertragsnummer", "vertragsauskunft"]):
            continue
        if re.match(r'^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+$', line):
            return line.replace(",", "")
    return None

def extract_text_from_pdf(file):
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        text = ""
        for page in doc:
            text += page.get_text()
        return text

st.title("📄 PDF-Umbenenner")
st.write("Lade PDF-Dateien hoch – sie werden automatisch nach dem Kundennamen (aus dem Adressblock) umbenannt und als ZIP-Datei zum Download bereitgestellt.")

uploaded_files = st.file_uploader("PDF-Dateien auswählen", type=["pdf"], accept_multiple_files=True)
if uploaded_files:
    renamed_files = []
    with zipfile.ZipFile("renamed_pdfs.zip", "w") as zipf:
        for uploaded_file in uploaded_files:
            text = extract_text_from_pdf(uploaded_file)
            customer_name = extract_customer_name(text)
            if not customer_name:
                st.warning(f"⚠️ Kein Name gefunden in: {uploaded_file.name}")
                continue
            new_filename = f"{customer_name}.pdf"
            zipf.writestr(new_filename, uploaded_file.getvalue())
            renamed_files.append(new_filename)
    if renamed_files:
        with open("renamed_pdfs.zip", "rb") as f:
            st.download_button("📥 ZIP-Datei herunterladen", f, file_name="renamed_pdfs.zip")
