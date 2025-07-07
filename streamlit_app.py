import streamlit as st
import fitz  # PyMuPDF
import os
import re

st.title("PDF-Umbenenner nach Kundennamen")

uploaded_files = st.file_uploader("PDF-Dateien hochladen", type=["pdf"], accept_multiple_files=True)

def extract_customer_name(text):
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if any(x in line.lower() for x in ["gmbh", "versicherung", "uniqa", "polizze", "vertragsnummer", "vertragsauskunft"]):
            continue
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+$", line):
            return line.replace(",", "")
    return None

if uploaded_files:
    output_dir = "umbenannt"
    os.makedirs(output_dir, exist_ok=True)

    for uploaded_file in uploaded_files:
        with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
            text = ""
            for page in doc:
                text += page.get_text()
        name = extract_customer_name(text)
        if name:
            new_filename = f"Vertragsauskunft {name}.pdf"
            output_path = os.path.join(output_dir, new_filename)
            with open(output_path, "wb") as f_out:
                f_out.write(uploaded_file.getbuffer())
            st.success(f"✅ {uploaded_file.name} → {new_filename}")
        else:
            st.error(f"❌ Kein Name gefunden in: {uploaded_file.name}")

    st.info("📁 Alle Dateien wurden in den Ordner 'umbenannt' gespeichert.")
