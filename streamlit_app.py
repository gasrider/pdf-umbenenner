
import streamlit as st
import fitz  # PyMuPDF
import zipfile
import os
import io

st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner nach Kundennamen")
st.write("Lade PDF-Dateien hoch – sie werden automatisch nach dem Kundennamen (aus dem Adressblock) umbenannt und als ZIP-Datei zum Download bereitgestellt.")

uploaded_files = st.file_uploader("PDF-Dateien hochladen", type=["pdf"], accept_multiple_files=True)

def extract_name_from_pdf(file):
    try:
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text = doc[0].get_text()
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        for i in range(len(lines) - 1):
            line1 = lines[i]
            line2 = lines[i + 1]
            full_name = f"{line1} {line2}"
            if (
                line1.istitle() and line2.istitle() and
                all(w[0].isupper() for w in full_name.split()) and
                not any(x in full_name for x in ["GmbH", "Finanz", "Versicherung", "Versand", "Beginn", "Ablauf", "Vertragsauskunft"])
            ):
                return full_name.replace(",", "").strip()
    except Exception:
        pass
    return None

if uploaded_files:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zip_file:
        for file in uploaded_files:
            name = extract_name_from_pdf(file)
            file.seek(0)
            if name:
                new_filename = f"Vertragsauskunft {name}.pdf"
                st.success(f"{file.name} → {new_filename}")
                zip_file.writestr(new_filename, file.read())
            else:
                st.warning(f"⚠️ Kein Name gefunden in: {file.name}")
    st.download_button("📦 ZIP-Datei herunterladen", zip_buffer.getvalue(), file_name="umbenannte_pdfs.zip")
