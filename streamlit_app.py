import streamlit as st
import fitz  # PyMuPDF
import os
import io
import zipfile

st.set_page_config(page_title="PDF-Umbenenner nach Kundennamen")

st.title("📄 PDF-Umbenenner nach Kundennamen")
st.write("Lade PDF-Dateien hoch – sie werden automatisch nach dem Kundennamen (über dem Adressblock) umbenannt und als ZIP-Datei bereitgestellt.")

uploaded_files = st.file_uploader("PDF-Dateien hochladen", type=["pdf"], accept_multiple_files=True)
output_dir = "umbenannt"
os.makedirs(output_dir, exist_ok=True)

def extract_name_from_text(text):
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if "straße" in line.lower() and i > 0:
            name_line = lines[i - 1].strip()
            # Firmen und irrelevante Zeilen überspringen
            if any(word in name_line.lower() for word in ["gmbh", "versicherung", "mondsee", "finanz"]):
                continue
            # Nur Zeilen mit zwei Wörtern (typischerweise Vorname + Nachname)
            parts = name_line.split()
            if len(parts) == 2 and all(p[0].isupper() for p in parts):
                return name_line
    return None

def sanitize_filename(name):
    # Entfernt unerlaubte Zeichen
    return "".join(c for c in name if c.isalnum() or c.isspace()).strip()

if uploaded_files:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for uploaded_file in uploaded_files:
            try:
                doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                text = doc[0].get_text()
                name = extract_name_from_text(text)
                if name:
                    safe_name = sanitize_filename(name)
                    new_filename = f"Vertragsauskunft {safe_name}.pdf"
                    output_path = os.path.join(output_dir, new_filename)
                    doc.save(output_path)
                    zipf.write(output_path, arcname=new_filename)
                    st.success(f"{uploaded_file.name} ➜ {new_filename}")
                else:
                    st.warning(f"⚠️ Kein Name gefunden in: {uploaded_file.name}")
            except Exception as e:
                st.error(f"Fehler bei Datei {uploaded_file.name}: {e}")
    zip_buffer.seek(0)
    st.download_button("📦 ZIP-Datei herunterladen", data=zip_buffer, file_name="umbenannte_pdfs.zip", mime="application/zip")
