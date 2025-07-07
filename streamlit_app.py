import streamlit as st
import os
import fitz  # PyMuPDF
import zipfile
import re

def extract_name_from_text(text):
    # Suche nach zwei aufeinanderfolgenden Groß-/Kleinwörtern, die keine Firmennamen enthalten
    lines = text.split('\n')
    for i in range(len(lines) - 1):
        line1 = lines[i].strip()
        line2 = lines[i + 1].strip()
        full_name = f"{line1} {line2}"

        if (
            re.match(r'^[A-ZÄÖÜ][a-zäöüß]+\s[A-ZÄÖÜ][a-zäöüß]+$', full_name) and
            "GmbH" not in full_name and
            "Versicherung" not in full_name and
            "Finanz" not in full_name
        ):
            return full_name

    return None

def process_pdf(uploaded_file):
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    first_page = doc.load_page(0)
    text = first_page.get_text()
    name = extract_name_from_text(text)
    return name

st.title("📄 PDF-Umbenenner nach Kundennamen")
st.write("Lade PDF-Dateien hoch – sie werden automatisch nach dem Kundennamen (aus dem Adressblock) umbenannt und als ZIP-Datei zum Download bereitgestellt.")

uploaded_files = st.file_uploader("PDF-Dateien hochladen", type="pdf", accept_multiple_files=True)
if uploaded_files:
    if not os.path.exists("umbenannt"):
        os.makedirs("umbenannt")

    with zipfile.ZipFile("umbenannt.zip", "w") as zipf:
        for uploaded_file in uploaded_files:
            name = process_pdf(uploaded_file)
            uploaded_file.seek(0)

            if name:
                clean_name = name.replace(",", "").replace(" ", "_")
                new_filename = f"Vertragsauskunft_{clean_name}.pdf"
                file_path = os.path.join("umbenannt", new_filename)

                with open(file_path, "wb") as f:
                    f.write(uploaded_file.read())

                zipf.write(file_path, arcname=new_filename)
                st.success(f"{uploaded_file.name} → {new_filename}")
            else:
                st.warning(f"⚠️ Kein Name gefunden in: {uploaded_file.name}")

    with open("umbenannt.zip", "rb") as f:
        st.download_button("📦 ZIP-Datei herunterladen", f, file_name="umbenannt.zip")
