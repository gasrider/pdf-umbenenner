import streamlit as st
import io, re, zipfile
from datetime import datetime

import fitz       # PyMuPDF
import pytesseract
from PIL import Image

# ─── OCR / Textextraktion ────────────────────────────────────────────────────
def extract_text_with_ocr(pdf_stream) -> str:
    doc = fitz.open(stream=pdf_stream.read(), filetype="pdf")
    full_text = ""
    for page in doc:
        txt = page.get_text().strip()
        if txt:
            full_text += txt + "\n"
        else:
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            full_text += pytesseract.image_to_string(img, lang="deu") + "\n"
    doc.close()
    return full_text

# ─── Bounding-Box Debugfunktion ──────────────────────────────────────────────
def debug_bbox(pdf_stream):
    """
    Listet alle Textblöcke in 12–28% der Seitenhöhe mit ihren y-Koordinaten.
    """
    pdf_stream.seek(0)
    doc = fitz.open(stream=pdf_stream.read(), filetype="pdf")
    page = doc[0]
    h = page.rect.height
    y_min, y_max = h*0.12, h*0.28
    blocks = page.get_text("dict")["blocks"]
    doc.close()

    entries = []
    for blk in blocks:
        y0, y1 = blk["bbox"][1], blk["bbox"][3]
        if y0 < y_min or y0 > y_max:
            continue
        # Fasse den Block-Text zusammen
        text = " ".join(
            span["text"]
            for line in blk["lines"]
            for span in line["spans"]
        ).strip()
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        entries.append((round(y0,1), text))
    return entries

# ─── Bounding-Box Name-Detection mit Blacklist ──────────────────────────────
def extract_name_by_bbox(pdf_stream, blacklist):
    pdf_stream.seek(0)
    doc = fitz.open(stream=pdf_stream.read(), filetype="pdf")
    page = doc[0]
    h = page.rect.height
    y_min, y_max = h*0.12, h*0.28
    blocks = page.get_text("dict")["blocks"]
    doc.close()

    for blk in blocks:
        y0 = blk["bbox"][1]
        if not (y_min < y0 < y_max):
            continue

        text = " ".join(
            span["text"]
            for line in blk["lines"]
            for span in line["spans"]
        ).strip()
        text = re.sub(r"\s+", " ", text)
        low = text.lower()

        # Überspringen, wenn Blacklist-Stichwort drin
        if any(kw in low for kw in blacklist):
            continue
        # Skip, falls Ziffern
        if re.search(r"\d", text):
            continue

        # Person (2–4 Wörter Groß) oder Firma (…GmbH)
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+(?: [A-ZÄÖÜ][a-zäöüß]+){1,3}$", text) \
        or text.endswith("GmbH"):
            return text

    return None

# ─── Heuristischer Fallback ──────────────────────────────────────────────────
def extract_name_fallback(text: str) -> str | None:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    street_kw = ["straße","strasse","weg","gasse","platz","allee"]
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in street_kw) and i>0:
            cand = lines[i-1]
            if re.match(r"^[A-Za-zÄÖÜäöüß ]+$", cand):
                return cand
    for line in lines:
        if "geb.datum" in line.lower():
            p = line.split("Geb.datum")[0].strip()
            if re.match(r"^[A-Za-zÄÖÜäöüß ]+$", p):
                return p
    for line in lines[:5]:
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+", line):
            return line
    return None

# ─── Gesamt-Extraktion ──────────────────────────────────────────────────────
def extract_customer_name(pdf_stream, blacklist):
    name = extract_name_by_bbox(pdf_stream, blacklist)
    if name:
        return name
    pdf_stream.seek(0)
    text = extract_text_with_ocr(pdf_stream)
    fb = extract_name_fallback(text)
    if fb:
        return fb
    return f"Unbekannt_{datetime.now():%Y%m%d%H%M%S}"

# ─── Dateiname sanitisieren ──────────────────────────────────────────────────
def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w]", "", name)

# ─── Streamlit UI ───────────────────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner Debug", layout="centered")
st.title("📄 PDF-Umbenenner Debug — Blacklist-Erstellung")

# Eingabe
uploads = st.file_uploader(
    "PDFs hochladen",
    type="pdf",
    accept_multiple_files=True
)
blacklist = st.text_area(
    "Blacklist-Wörter (kommagetrennt)",
    value="mondsee,finanz,rainerstraße,5310,gmbh"
).split(",")

debug = st.checkbox("🔍 Debug: Alle Textblöcke im Header-Bereich anzeigen")

if uploads:
    if debug:
        st.subheader("⚙️ Debug-Ausgabe: Kandidaten im 12–28% Bereich")
        for pdf in uploads:
            st.write(f"**{pdf.name}**")
            entries = debug_bbox(pdf)
            for y0, txt in entries:
                st.write(f"  • y0={y0} → {txt}")
        st.stop()

    # Produktiv-Modus
    results, errors = [], []
    with st.spinner("Verarbeite..."):
        for pdf in uploads:
            pdf.seek(0)
            cust = extract_customer_name(pdf, [w.lower().strip() for w in blacklist])
            if cust.startswith("Unbekannt_"):
                errors.append(pdf.name)
            new_fn = f"Vertragsauskunft{sanitize_filename(cust)}.pdf"
            pdf.seek(0)
            results.append((pdf.name, new_fn, pdf.read()))

    st.subheader("📂 Vorschau der neuen Dateinamen")
    for orig, new, _ in results:
        st.write(f"• **{orig}** ➔ {new}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for _, new, data in results:
            zf.writestr(new, data)
    buf.seek(0)

    st.download_button("📦 ZIP herunterladen", buf, "umbenannte_pdfs.zip", "application/zip")

    if errors:
        st.warning("⚠️ Nicht benennbar:")
        for e in errors:
            st.write(f"- {e}")
