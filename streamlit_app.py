import streamlit as st
import os
import fitz  # PyMuPDF
import re
import shutil
import zipfile
from io import BytesIO

st.set_page_config(page_title="PDF-Umbenenner", page_icon="📄")
st.title("📄 PDF-Umbenenner nach Kundennamen")
st.markdown("Erkennt Kundennamen oberhalb der Adresse – Firmen oder Privatpersonen.")

uploaded_files = st.file_uploader("PDF-Dateien hochladen", type="pdf", accept_multiple_files=True)

# Absender, die ignoriert werden sollen
IGNORED_LINES = {"Mondsee Finanz GmbH", "UNIQA Österreich Versicherungen AG"}

# Adressmuster zum Erkennen (Deutsch)
ADDRESS_KEYWORDS = r"\b(straße|strasse|gasse|weg|platz|allee|ring|gürtel|siedlung|zeile)\b"

def extract_customer_name(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lines = [line for line in lines if line not in IGNORED_LINES]

    for i in range(1, len(lines)):
        current_line = lines[i].lower()
        if re.search(ADDRESS_KEYWORDS, current_line):
            possible_name = lines[i - 1]
            if 3 <= len(possible_name) <= 60:  # Minimale Länge, um irrelevante Zeilen auszuschließen
                return possible_name
    return None

if uploaded_files:
    output_dir = "umbenannt"
    os.makedirs(output_dir, exist_ok=True)
    messages = []

    for file in uploaded_files:
        pdf_bytes = file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(0)
        text = page.get_text("text")
        name = extract_customer_name(text)

        if name:
            name_clean = re.sub(r'[^\wäöüÄÖÜß\s-]', '', name)  # keine Sonderzeichen
            name_clean = re.sub(r'\s+', ' ', name_clean).strip()
            new_filename = f"Vertragsauskunft {name_clean}.pdf"
            output_path = os.path.join(output_dir, new_filename)
            with open(output_path, "wb") as f_out:
                f_out.write(pdf_bytes)
            messages.append(f"✅ {file.name} → {new_filename}")
        else:
            messages.append(f"⚠️ Kein Kundenname gefunden in: {file.name}")

    # ZIP-Datei erstellen
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        for filename in os.listdir(output_dir):
            zip_file.write(os.path.join(output_dir, filename), arcname=filename)
    zip_buffer.seek(0)

    for msg in messages:
        st.markdown(msg)

    st.download_button("📦 ZIP-Datei herunterladen", zip_buffer, file_name="umbenannte_pdfs.zip", mime="application/zip")
