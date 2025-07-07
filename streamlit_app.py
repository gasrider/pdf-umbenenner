import streamlit as st
import os
import re
from pathlib import Path
from PyPDF2 import PdfReader
from io import BytesIO
import zipfile

def extract_customer_name(text: str) -> str:
    lines = text.splitlines()

    # 1. Firmenname mit GmbH, AG etc.
    for line in lines:
        if re.search(r"\b(GmbH|AG|KG|e\.U\.)\b", line) and "Mondsee Finanz" not in line:
            return line.strip()

    # 2. Geburtsdatum-Zeile -> Name davor
    for line in lines:
        if "Geb.datum" in line:
            name = line.split("Geb.datum")[0].strip()
            if len(name.split()) >= 2:
                return name

    # 3. E-Mail-Adresse -> Namen extrahieren
    for line in lines:
        email_match = re.search(r'([a-zA-Z0-9._%+-]+)@', line)
        if email_match:
            raw = email_match.group(1).replace(".", " ").replace("_", " ")
            name = " ".join(w.capitalize() for w in raw.split())
            return name

    # 4. Zeile vor Adresse erkennen (Straße etc.)
    for i, line in enumerate(lines):
        if re.search(r"\b(straße|strasse|weg|platz|gasse)\b", line.lower()) and i > 0:
            return lines[i - 1].strip()

    return "Unbekannter Kunde"

def sanitize_filename(name: str) -> str:
    name = name.replace(",", "")
    name = re.sub(r"\s+", " ", name).strip()
    return f"Vertragsauskunft {name}"

def process_pdf(file) -> (str, BytesIO):
    reader = PdfReader(file)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    customer_name = extract_customer_name(text)
    filename = sanitize_filename(customer_name) + ".pdf"
    return filename, file

def main():
    st.title("PDF Umbenenner nach Kundennamen")
    uploaded_files = st.file_uploader("PDF-Dateien hochladen", type=["pdf"], accept_multiple_files=True)

    if uploaded_files:
        with BytesIO() as zip_buffer:
            with zipfile.ZipFile(zip_buffer, "w") as zipf:
                for uploaded_file in uploaded_files:
                    filename, filedata = process_pdf(uploaded_file)
                    zipf.writestr(filename, filedata.read())
            st.download_button(
                label="ZIP-Datei mit umbenannten PDFs herunterladen",
                data=zip_buffer.getvalue(),
                file_name="umbenannte_pdfs.zip",
                mime="application/zip"
            )

if __name__ == "__main__":
    main()
