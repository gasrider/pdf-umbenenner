
import streamlit as st
import fitz  # PyMuPDF
import os
import zipfile
import re

UPLOAD_FOLDER = "uploads"
RENAMED_FOLDER = "umbenannt"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RENAMED_FOLDER, exist_ok=True)

def extract_name_from_pdf(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        first_page_text = doc[0].get_text()
        doc.close()

        lines = [line.strip() for line in first_page_text.splitlines()]
        for i in range(1, len(lines) - 1):
            curr_line = lines[i].strip()
            next_line = lines[i + 1].strip()
            prev_line = lines[i - 1].strip() if i > 0 else ""

            # Suche nach Adresse
            if re.search(r"\d{4,5}\s+\w+", next_line) and re.search(r"(straße|gasse|weg|platz|allee)", curr_line, re.IGNORECASE):
                # Name ist entweder direkt davor oder in Zeile -2, wenn dazwischen leer ist
                if prev_line:
                    if prev_line != "":
                        return prev_line.strip()
                    elif i >= 2:
                        return lines[i - 2].strip()
    except Exception as e:
        print(f"Fehler beim Lesen von {pdf_path}: {e}")
    return None

def save_uploaded_file(uploaded_file):
    file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

def zip_files(folder_path, zip_name="umbenannt.zip"):
    zip_path = os.path.join(folder_path, "..", zip_name)
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            zipf.write(file_path, arcname=filename)
    return zip_path

st.set_page_config(page_title="PDF-Umbenenner nach Kundennamen", page_icon="📄")
st.title("📄 PDF-Umbenenner nach Kundennamen")
st.markdown("Lade PDF-Dateien hoch – sie werden automatisch nach dem Kundennamen (über dem Adressblock) umbenannt und als ZIP-Datei zum Download bereitgestellt.")

uploaded_files = st.file_uploader("PDF-Dateien hochladen", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    renamed_files = []
    for uploaded_file in uploaded_files:
        saved_path = save_uploaded_file(uploaded_file)
        name = extract_name_from_pdf(saved_path)
        if name:
            name_clean = name.replace(",", "").replace("/", "").strip()
            new_filename = f"Vertragsauskunft {name_clean}.pdf"
            new_path = os.path.join(RENAMED_FOLDER, new_filename)
            with open(saved_path, "rb") as src, open(new_path, "wb") as dst:
                dst.write(src.read())
            renamed_files.append((uploaded_file.name, new_filename))
            st.success(f"{uploaded_file.name} → {new_filename}")
        else:
            st.warning(f"⚠️ Kein Name gefunden in: {uploaded_file.name}")

    if renamed_files:
        zip_path = zip_files(RENAMED_FOLDER)
        with open(zip_path, "rb") as f:
            st.download_button(
                label="📦 ZIP-Datei herunterladen",
                data=f,
                file_name="umbenannte_pdfs.zip",
                mime="application/zip"
            )
