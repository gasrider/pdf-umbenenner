import streamlit as st
import fitz  # PyMuPDF
import os
import re
import tempfile
from zipfile import ZipFile

st.set_page_config(page_title="PDF-Umbenenner", layout="centered")

st.title("📄 PDF Umbenenner nach Kundennamen")
st.caption("PDF-Dateien hochladen")

uploaded_files = st.file_uploader("Drag and drop files here", type=["pdf"], accept_multiple_files=True)

def extract_customer_name(text):
    lines = text.split("\n")
    lines = [line.strip() for line in lines if line.strip()]

    address_keywords = ["straße", "weg", "gasse", "platz", "gürtel", "steig", "zeile", "siedlung", "top"]
    blacklist_keywords = ["versicherung", "vertragsauskunft", "beginn", "ablauf", "ag", "gmbh", "versicherungsmakler"]

    for i, line in enumerate(lines):
        for word in address_keywords:
            if word in line.lower():
                for offset in range(1, 4):
                    if i - offset >= 0:
                        possible_name = lines[i - offset]
                        if all(bw not in possible_name.lower() for bw in blacklist_keywords):
                            return possible_name.replace(",", "").strip()
    return None

if uploaded_files:
    with tempfile.TemporaryDirectory() as tmpdir:
        result_paths = []
        umbenennungen = []

        for file in uploaded_files:
            original_path = os.path.join(tmpdir, file.name)
            with open(original_path, "wb") as f:
                f.write(file.getbuffer())

            doc = fitz.open(original_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()

            customer_name = extract_customer_name(text)
            if not customer_name:
                customer_name = "Kundevertrag"

            safe_name = customer_name.replace(" ", "").replace(",", "")
            new_filename = f"Vertragsauskunft{safe_name}.pdf"
            new_path = os.path.join(tmpdir, new_filename)
            os.rename(original_path, new_path)
            result_paths.append((new_filename, new_path))
            umbenennungen.append(f"{file.name} ➜ {new_filename}")

        zip_path = os.path.join(tmpdir, "umbenannte_pdfs.zip")
        with ZipFile(zip_path, "w") as zipf:
            for filename, path in result_paths:
                zipf.write(path, arcname=filename)

        st.markdown("**🔍 Vorschau der umbenannten Dateien:**")
        for umbenennung in umbenennungen:
            st.write(f"• {umbenennung}")

        with open(zip_path, "rb") as f:
            st.download_button(
                label="📥 ZIP-Datei mit umbenannten PDFs herunterladen",
                data=f,
                file_name="umbenannte_pdfs.zip",
                mime="application/zip"
            )

