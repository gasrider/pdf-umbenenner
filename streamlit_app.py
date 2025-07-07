import streamlit as st
import io
import re
import zipfile
from datetime import datetime

import fitz       # PyMuPDF
import pytesseract
from PIL import Image

# ─── OCR mit Fallback ─────────────────────────────────────────────────────────
def extract_text_with_ocr(pdf_stream) -> str:
    pdf_stream.seek(0)
    doc = fitz.open(stream=pdf_stream.read(), filetype="pdf")
    out = ""
    for page in doc:
        txt = page.get_text().strip()
        if txt:
            out += txt + "\n"
        else:
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            out += pytesseract.image_to_string(img, lang="deu") + "\n"
    doc.close()
    return out

# ─── Name im engen gelben Bereich extrahieren ────────────────────────────────
def extract_name_in_yellow(pdf_stream) -> str | None:
    pdf_stream.seek(0)
    doc = fitz.open(stream=pdf_stream.read(), filetype="pdf")
    page = doc[0]
    w, h = page.rect.width, page.rect.height
    blocks = page.get_text("dict")["blocks"]
    doc.close()

    # genau gelb markierter Bereich
    y_min, y_max = h * 0.12, h * 0.18
    x_min, x_max = w * 0.45, w * 0.85

    for blk in blocks:
        x0, y0, _, _ = blk["bbox"]
        if not (x_min < x0 < x_max and y_min < y0 < y_max):
            continue

        txt = " ".join(
            span["text"]
            for line in blk["lines"]
            for span in line["spans"]
        ).strip()
        txt = re.sub(r"\s+", " ", txt)

        # überspringe, falls Ziffern (PLZ, Datum etc.)
        if re.search(r"\d", txt):
            continue

        # Privatperson (2–4 Wörter) oder Firma (…GmbH)
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+(?: [A-ZÄÖÜ][a-zäöüß]+){1,3}$", txt) \
        or txt.endswith("GmbH"):
            return txt

    return None

# ─── Heuristischer Fallback ──────────────────────────────────────────────────
def extract_name_fallback(text: str) -> str | None:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    street_kw = ["straße","strasse","weg","gasse","platz","allee"]

    # Name über Adresse
    for i,line in enumerate(lines):
        if any(kw in line.lower() for kw in street_kw) and i>0:
            cand = lines[i-1]
            if re.match(r"^[A-Za-zÄÖÜäöüß ]+$", cand):
                return cand

    # Zeile mit Geb.datum
    for line in lines:
        if "geb.datum" in line.lower():
            p = line.split("geb.datum")[0].strip()
            if re.match(r"^[A-Za-zÄÖÜäöüß ]+$", p):
                return p

    # Erste fünf Zeilen
    for line in lines[:5]:
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+", line):
            return line

    return None

# ─── Gesamt-Extraktion ──────────────────────────────────────────────────────
def extract_customer_name(pdf_stream) -> str:
    # 1) Gelber Bereich
    name = extract_name_in_yellow(pdf_stream)
    if name:
        return name

    # 2) OCR + Fallback
    text = extract_text_with_ocr(pdf_stream)
    name2 = extract_name_fallback(text)
    if name2:
        return name2

    # 3) Zeitstempel
    return f"Unbekannt_{datetime.now():%Y%m%d%H%M%S}"

# ─── Bereinige Dateinamen (Spaces bleiben) ───────────────────────────────────
def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w\s]", "", name)

# ─── Streamlit UI ───────────────────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner (exakter gelber Bereich)")

files = st.file_uploader("PDFs hochladen (max. 200 MB/Datei)", type="pdf", accept_multiple_files=True)
if files:
    results, errors = [], []
    with st.spinner("Verarbeite…"):
        for f in files:
            f.seek(0)
            cust = extract_customer_name(f)
            if cust.startswith("Unbekannt_"):
                errors.append(f.name)
            safe = sanitize_filename(cust)
            new = f"Vertragsauskunft {safe}.pdf"
            f.seek(0)
            data = f.read()
            results.append((f.name, new, data))

    st.subheader("🔍 Vorschau der Dateinamen")
    for orig,new,_ in results:
        st.write(f"• **{orig}** ➔ {new}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf,"w") as zf:
        for _,new,data in results:
            zf.writestr(new,data)
    buf.seek(0)

    st.download_button("📦 ZIP herunterladen", buf, "umbenannte_pdfs.zip", "application/zip")

    if errors:
        st.warning("⚠️ Kein Name gefunden für:")
        for e in errors:
            st.write(f"- {e}")
