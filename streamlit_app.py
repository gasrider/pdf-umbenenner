
import streamlit as st
import fitz  # PyMuPDF
import zipfile
import os
import re
from io import BytesIO

# Titel und Beschreibung
st.title("📄 PDF-Umbenenner nach Kundennamen")
st.write("Lade PDF-Dateien hoch – sie werden automatisch nach dem Kundennamen (aus dem Adressblock) umbenannt und als ZIP-Datei zum Download bereitgestellt.")

# Ordner für umbenannte PDFs
os.makedirs("umbenannt", exist_ok=True)

# Upload
uploaded_files = st.file_uploader("PDF-Dateien hochladen", type="pdf", accept_multiple_files=True)

def extract_name_from_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()

    # Suche nach typischen Namen (z. B. „Max Mustermann“) mit Großbuchstaben
    matches = re.findall(r"\b([A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+)\b", text)

    # Entferne bekannte unerwünschte Namen
    blacklist = ["Mondsee Finanz GmbH", "UNIQA", "Versicherungsanstalt"]

    for name in matches:
        if all(bad not in name for bad in blacklist):
            return name.strip()

    return None

# Verarbeitung
if uploaded_files:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        for uploaded_file in uploaded_files:
            name = extract_name_from_pdf(uploaded_file)

            if name:
                safe_name = re.sub(r"[^\w\s-]", "", name)  # keine Sonderzeichen
                new_filename = f"{uploaded_file.name} → Vertragsauskunft {safe_name}.pdf"
                file_bytes = uploaded_file.getvalue()
                zip_file.writestr(f"umbenannt/Vertragsauskunft {safe_name}.pdf", file_bytes)
                st.success(new_filename)
            else:
                st.warning(f"⚠️ Kein Name gefunden in: {uploaded_file.name}")

    st.download_button("📦 ZIP-Datei herunterladen", data=zip_buffer.getvalue(), file_name="umbenannte_pdfs.zip", mime="application/zip")
