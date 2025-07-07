import streamlit as st
import os
import fitz  # PyMuPDF
import zipfile
import io
import re
from datetime import datetime

def extract_customer_name(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        blocks = page.get_text("dict")["blocks"]
        name_candidates = []

        for block in blocks:
            if "lines" in block and block["bbox"][1] < 300:  # Oberer Teil der Seite
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        if 300 < span["bbox"][0] < 550:  # Rechte obere Hälfte
                            if (
                                3 <= len(text.split()) <= 5 and
                                not any(word.lower() in text.lower() for word in ["straße", "gasse", "versichert", "monatlich", "beginn", "vertrag", "geburtsdatum", "versnr", "finanz", "gmbh", "betrag", "eur"])
                            ):
                                name_candidates.append(text)

        doc.close()
        if name_candidates:
            return name_candidates[0]
        else:
            return None
    except Exception as e:
        return None

def sanitize_filename(name):
    # Entfernt unerwünschte Zeichen und ersetzt Leerzeichen durch _
    return re.sub(r"[^\w\s-]", "", name).replace(" ", "").strip()

st.title("📄 PDF Umbenenner nach Kundennamen")
uploaded_files = st.file_uploader("PDF-Dateien hochladen", type="pdf", accept_multiple_files=True)

if uploaded_files:
    renamed_pdfs = []
    errors = []

    with st.spinner("Verarbeite PDFs..."):
        for uploaded_file in uploaded_files:
            input_pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            temp_pdf_path = f"/tmp/{uploaded_file.name}"
            input_pdf.save(temp_pdf_path)

            name = extract_customer_name(temp_pdf_path)
            if name:
                filename = sanitize_filename(name) + ".pdf"
            else:
                filename = f"Unbekannt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                errors.append(uploaded_file.name)

            buffer = io.BytesIO()
            input_pdf.save(buffer)
            buffer.seek(0)
            renamed_pdfs.append((filename, buffer))

    with io.BytesIO() as zip_buffer:
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            for filename, pdf_buffer in renamed_pdfs:
                zip_file.writestr(filename, pdf_buffer.read())
        zip_buffer.seek(0)
        st.success("✅ Umbenennung abgeschlossen.")
        st.download_button(
            label="📦 ZIP-Datei herunterladen",
            data=zip_buffer,
            file_name="umbenannte_pdfs.zip",
            mime="application/zip"
        )

    st.subheader("📋 Vorschau der erkannten Namen")
    for (filename, _), original_file in zip(renamed_pdfs, uploaded_files):
        st.markdown(f"**{original_file.name}** ➝ `{filename}`")

    if errors:
        st.warning("⚠️ Bei folgenden Dateien konnte kein Name erkannt werden:")
        for err in errors:
            st.markdown(f"- {err}")
