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

    # Entferne bekannte Absender wie "Mondsee Finanz GmbH"
    full_text = full_text.replace("Mondsee Finanz GmbH", "")

    # Suche nach einem typischen Namen, z. B. mittig im Dokument
    matches = re.findall(r"\b([A-ZÄÖÜ][a-zäöüß]+)\s+([A-ZÄÖÜ][a-zäöüß]+)\b", full_text)

    # Filtere bekannte Wörter oder Begriffe heraus
    blacklist = {"Vertragsauskunft", "GmbH", "Herr", "Frau", "Straße", "Versicherung", "UNIQA"}

    for vorname, nachname in matches:
        if vorname not in blacklist and nachname not in blacklist:
            return f"Vertragsauskunft {nachname}, {vorname}.pdf"

    return None

st.title("📄 PDF-Umbenenner")
st.write("Lade PDF-Dateien hoch – sie werden automatisch nach enthaltenem Kundennamen umbenannt und als ZIP-Datei zum Download bereitgestellt.")

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
