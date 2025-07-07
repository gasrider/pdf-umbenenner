import streamlit as st
import fitz  # PyMuPDF
import os
import shutil
import re
from pathlib import Path
from zipfile import ZipFile

st.set_page_config(page_title="PDF-Umbenenner nach Kundennamen")

st.title("📄 PDF-Umbenenner nach Kundennamen")
st.markdown("Lade PDF-Dateien hoch – sie werden automatisch nach dem Kundennamen (aus dem Adressblock) "
            "umbenannt und als ZIP-Datei zum Download bereitgestellt.")

uploaded_files = st.file_uploader("PDF-Dateien hochladen", type="pdf", accept_multiple_files=True)

output_dir = Path("umbenannt")
output_dir.mkdir(exist_ok=True)

def extract_customer_name(text):
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if "Vertragsauskunft" in line:
            # Suche in den nächsten 5 Zeilen nach einem passenden Namen
            for j in range(i+1, min(i+6, len(lines))):
                name_line = lines[j].strip()
                if len(name_line.split()) >= 2 and not any(char.isdigit() for char in name_line):
                    return "Vertragsauskunft " + name_line.replace(",", "")
    return None

if uploaded_files:
    output_dir.mkdir(exist_ok=True)
    for uploaded_file in uploaded_files:
        with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
            text = ""
            for page in doc:
                text += page.get_text()
        name = extract_customer_name(text)
        if name:
            new_filename = f"{name}.pdf"
            file_path = output_dir / new_filename
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"{uploaded_file.name} → {new_filename}")
        else:
            st.warning(f"⚠️ Kein Name gefunden in: {uploaded_file.name}")

    if any(output_dir.iterdir()):
        zip_path = "umbenannte_pdfs.zip"
        with ZipFile(zip_path, "w") as zipf:
            for file in output_dir.iterdir():
                zipf.write(file, arcname=file.name)
        with open(zip_path, "rb") as f:
            st.download_button("📦 ZIP-Datei herunterladen", f, file_name="umbenannte_pdfs.zip")

    shutil.rmtree(output_dir)
