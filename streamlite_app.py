
import streamlit as st
import fitz  # PyMuPDF
import os

def extract_customer_name_from_pdf_enhanced(file_path):
    import re
    address_keywords = ["straße", "weg", "gasse", "platz", "gürtel", "steig", "zeile", "siedlung"]
    blacklist_keywords = ["versicherung", "vertragsauskunft", "beginn", "ablauf", "ag", "gmbh", "versicherungsmakler"]
    fallback_pattern = re.compile(r"\b[A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?\b")

    doc = fitz.open(file_path)
    for page in doc:
        text = page.get_text("text")
        lines = text.splitlines()

        for i, line in enumerate(lines):
            if any(kw in line.lower() for kw in address_keywords):
                for offset in range(1, 4):
                    name_index = i - offset
                    if name_index < 0:
                        continue
                    candidate = lines[name_index].strip()

                    if (
                        1 <= len(candidate.split()) <= 5 and
                        any(c.isupper() for c in candidate) and
                        not any(bkw in candidate.lower() for bkw in blacklist_keywords) and
                        not candidate.strip().endswith(".")
                    ):
                        return candidate.replace(",", "")

        # Fallback: Suche nach klassischem Namen
        fallback_matches = fallback_pattern.findall(text)
        for match in fallback_matches:
            if not any(bkw in match.lower() for bkw in blacklist_keywords):
                return match.replace(",", "")
    return None

st.title("PDF-Umbenenner nach Kundennamen")

uploaded_files = st.file_uploader("Lade eine oder mehrere PDF-Dateien hoch", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    output_dir = "umbenannt"
    os.makedirs(output_dir, exist_ok=True)
    for uploaded_file in uploaded_files:
        with open(uploaded_file.name, "wb") as f:
            f.write(uploaded_file.getbuffer())
        name = extract_customer_name_from_pdf_enhanced(uploaded_file.name)
        if name:
            new_filename = f"Vertragsauskunft {name}.pdf".replace(" ", "")
        else:
            new_filename = f"Vertragsauskunft_Unbekannt.pdf"
        new_path = os.path.join(output_dir, new_filename)
        os.rename(uploaded_file.name, new_path)
        st.success(f"{uploaded_file.name} ➤ {new_filename}")
