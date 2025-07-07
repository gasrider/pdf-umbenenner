import streamlit as st
import os
import fitz  # PyMuPDF
import re
import shutil
import zipfile
from io import BytesIO

st.set_page_config(page_title="PDF-Umbenenner", page_icon="📄")
st.title("📄 PDF-Umbenenner nach Kundennamen")
st.markdown("Erkennt Kundennamen aus PDF-Dokumenten – Firmen oder Privatpersonen.")

uploaded_files = st.file_uploader("PDF-Dateien hochladen", type="pdf", accept_multiple_files=True)

# Diese Namen sollen ignoriert werden (z. B. Absender)
ABZUSCHNEIDEN = {"Mondsee Finanz GmbH", "UNIQA Österreich Versicherungen AG"}

def extract_customer_name(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lines = [line for line in lines if line not in ABZUSCHNEIDEN]

    for i, line in enumerate(lines):
        # Sonderfall Firmenname mit GmbH, OG, etc.
        if re.search(r'\b(GmbH|AG|OG|KG|e\.U\.)\b', line) and not any(ign in line for ign in ABZUSCHNEIDEN):
            return line

        # Privatperson über Adresse
        if i + 1 < len(lines):
            next_line = lines[i + 1].lower()
            if re.search(r'\bstraße\b|\bstrasse\b|\bweg\b|\bplatz\b|\bgasse\b', next_line):
                if re.match(r'^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+$', line):
                    return line
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
            name_clean = re.sub(r'[^\wäöüÄÖÜß\s-]', '', name).strip()
            name_clean = re.sub(r'\s+', ' ', name_clean)
            new_filename = f"Vertragsauskunft {name_clean}.pdf"
            output_path = os.path.join(output_dir, new_filename)
            with open(output_path, "wb") as f_out:
                f_out.write(pdf_bytes)
            messages.append(f"✅ {file.name} → {new_filename}")
        else:
            messages.append(f"⚠️ Kein Kundenname gefunden in: {file.name}")

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        for filename in os.listdir(output_dir):
            zip_file.write(os.path.join(output_dir, filename), arcname=filename)
    zip_buffer.seek(0)

    for msg in messages:
        st.markdown(msg)

    st.download_button("📦 ZIP-Datei herunterladen", zip_buffer, file_name="umbenannte_pdfs.zip", mime="application/zip")
