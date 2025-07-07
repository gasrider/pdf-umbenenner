import streamlit as st
import fitz  # PyMuPDF
import os
import io
import zipfile

st.set_page_config(page_title="PDF-Umbenenner nach Kundennamen")

st.title("📄 PDF-Umbenenner nach Kundennamen")
st.write("Lade PDF-Dateien hoch – sie werden automatisch nach dem Kundennamen (aus dem Adressblock) umbenannt und als ZIP-Datei bereitgestellt.")

uploaded_files = st.file_uploader("PDF-Dateien hochladen", type=["pdf"], accept_multiple_files=True)
output_dir = "umbenannt"
os.makedirs(output_dir, exist_ok=True)

def extract_name_from_region(page):
    # Begrenze Region im oberen Drittel der Seite (mittig)
    width, height = page.rect.width, page.rect.height
    region = fitz.Rect(width * 0.25, height * 0.05, width * 0.75, height * 0.30)
    words = page.get_text("words")  # Liste der Wörter mit Positionen
    lines = {}
    for w in words:
        x0, y0, x1, y1, word, block_no, line_no, word_no = w
        if region.contains(fitz.Rect(x0, y0, x1, y1)):
            lines.setdefault(line_no, []).append(word)
    name_candidates = []
    for line in lines.values():
        line_text = " ".join(line)
        # nur zwei Wörter (Vorname Nachname), keine Firmennamen
        if 1 < len(line) <= 3 and all(w[0].isupper() for w in line):
            if not any(x in line_text.lower() for x in ["gmbh", "versicherung", "finanz", "gesellschaft"]):
                name_candidates.append(line_text.strip())
    return name_candidates[0] if name_candidates else None

def sanitize_filename(name):
    return "".join(c for c in name if c.isalnum() or c.isspace()).strip()

if uploaded_files:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for uploaded_file in uploaded_files:
            try:
                doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                page = doc[0]
                name = extract_name_from_region(page)
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
