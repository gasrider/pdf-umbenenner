import streamlit as st
import os
import io
import zipfile
from PyPDF2 import PdfReader
import re

def extract_customer_name(text):
    ignore_keywords = ["GmbH", "Versicherung", "Finanz", "UNIQA", "AG", "Gesellschaft", "OG", "mbH", "Mondsee"]
    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        if not line or any(keyword in line for keyword in ignore_keywords):
            continue
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+$", line):
            return line
    return None

def main():
    st.set_page_config(page_title="PDF-Umbenenner", page_icon="📄")
    st.title("📄 PDF-Umbenenner nach Kundennamen")
    st.write("Lade PDF-Dateien hoch – sie werden automatisch nach dem Kundennamen (aus dem Adressblock) umbenannt und als ZIP-Datei zum Download bereitgestellt.")

    uploaded_files = st.file_uploader("PDF-Dateien hochladen", type=["pdf"], accept_multiple_files=True)
    if uploaded_files:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zip_file:
            for uploaded_file in uploaded_files:
                pdf_reader = PdfReader(uploaded_file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() or ""
                name = extract_customer_name(text)
                if name:
                    name = name.replace(",", "")
                    new_filename = f"Vertragsauskunft {name}.pdf"
                    zip_file.writestr(new_filename, uploaded_file.read())
                    st.success(f"{uploaded_file.name} → {new_filename}")
                else:
                    st.warning(f"⚠️ Kein Name gefunden in: {uploaded_file.name}")

        st.download_button(
            label="📦 ZIP-Datei herunterladen",
            data=zip_buffer.getvalue(),
            file_name="umbenannte_pdfs.zip",
            mime="application/zip"
        )

if __name__ == "__main__":
    main()