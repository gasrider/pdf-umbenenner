import os
os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
import tempfile
import re
import zipfile

def extract_name_from_pdf(reader):
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() or ""

    # Entferne bekannte Firmennamen
    full_text = full_text.replace("Mondsee Finanz GmbH", "")

    # Sucht nach einem Namen (2 Wörter) vor einer Adresse (Straße, Hausnummer, PLZ)
    lines = full_text.split("\n")
    for i in range(len(lines) - 2):
        name_line = lines[i].strip()
        address_line = lines[i + 1].strip()
        plz_line = lines[i + 2].strip()

        if (re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+$", name_line) and
            re.search(r"(Straße|Weg|Gasse|Platz|Allee|Ring)", address_line) and
            re.match(r"^\d{4,5} ", plz_line)):
            vorname, nachname = name_line.split(" ", 1)
            return f"Vertragsauskunft {nachname}, {vorname}.pdf"

    return None

st.title("📄 PDF-Umbenenner")
st.write("Lade PDF-Dateien hoch – sie werden automatisch nach dem Kundennamen (aus dem Adressblock) umbenannt und als ZIP-Datei zum Download bereitgestellt.")

uploaded_files = st.file_uploader("PDF-Dateien auswählen", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    with tempfile.TemporaryDirectory() as temp_dir:
        renamed_files = []

        for uploaded_file in uploaded_files:
            input_path = os.path.join(temp_dir, uploaded_file.name)
            with open(input_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            reader = PdfReader(input_path)
            new_filename = extract_name_from_pdf(reader)

            if new_filename:
                output_path = os.path.join(temp_dir, new_filename)
                writer = PdfWriter()
                for page in reader.pages:
                    writer.add_page(page)
                with open(output_path, "wb") as out_f:
                    writer.write(out_f)
                renamed_files.append((new_filename, output_path))
            else:
                st.warning(f"⚠️ Kein Name gefunden in: {uploaded_file.name}")

        if renamed_files:
            zip_path = os.path.join(temp_dir, "umbenannte_pdfs.zip")
            with zipfile.ZipFile(zip_path, "w") as zipf:
                for name, path in renamed_files:
                    zipf.write(path, arcname=name)

            with open(zip_path, "rb") as f:
                st.download_button(
                    label="📥 ZIP mit umbenannten PDFs herunterladen",
                    data=f,
                    file_name="umbenannte_pdfs.zip",
                    mime="application/zip"
                )
