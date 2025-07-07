import streamlit as st
import io, re, zipfile
from datetime import datetime

import fitz       # PyMuPDF
import pytesseract
from PIL import Image

# ─── OCR / Textextraktion ────────────────────────────────────────────────────
def extract_text_with_ocr(pdf_stream) -> str:
    doc = fitz.open(stream=pdf_stream.read(), filetype="pdf")
    full = ""
    for page in doc:
        txt = page.get_text().strip()
        if txt:
            full += txt + "\n"
        else:
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            full += pytesseract.image_to_string(img, lang="deu") + "\n"
    doc.close()
    return full

# ─── Debug-Bounding-Boxes sammeln ────────────────────────────────────────────
def collect_header_texts(pdf_stream):
    """
    Alle Textblöcke aus 12–28 % Seitenhöhe.
    """
    pdf_stream.seek(0)
    doc = fitz.open(stream=pdf_stream.read(), filetype="pdf")
    page = doc[0]
    h = page.rect.height
    blocks = page.get_text("dict")["blocks"]
    doc.close()

    y_min, y_max = h*0.12, h*0.28
    texts = []
    for blk in blocks:
        y0 = blk["bbox"][1]
        if not (y_min < y0 < y_max):
            continue
        text = " ".join(
            span["text"] for line in blk["lines"] for span in line["spans"]
        ).strip()
        #  normalize spaces
        text = re.sub(r"\s+", " ", text)
        if text:
            texts.append(text)
    return texts

# ─── Bounding-Box-Name-Extraktion ────────────────────────────────────────────
def extract_name_by_bbox(pdf_stream, blacklist:set[str]) -> str | None:
    """
    Erster Kandidat im 12–28% Bereich, 
    der nicht in blacklist ist und keine Ziffern enthält.
    """
    pdf_stream.seek(0)
    doc = fitz.open(stream=pdf_stream.read(), filetype="pdf")
    page = doc[0]
    h = page.rect.height
    blocks = page.get_text("dict")["blocks"]
    doc.close()

    y_min, y_max = h*0.12, h*0.28
    for blk in blocks:
        y0 = blk["bbox"][1]
        if not (y_min < y0 < y_max):
            continue

        text = " ".join(
            span["text"] for line in blk["lines"] for span in line["spans"]
        ).strip()
        text = re.sub(r"\s+", " ", text)
        low = text.lower()

        # skip blacklist or digits
        if text in blacklist or re.search(r"\d", text):
            continue

        # Privatperson (2–4 Wörter) oder Firma (endet auf GmbH)
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+(?: [A-ZÄÖÜ][a-zäöüß]+){1,3}$", text)\
        or text.endswith("GmbH"):
            return text

    return None

# ─── Heuristischer Fallback ──────────────────────────────────────────────────
def extract_name_fallback(text: str) -> str | None:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    street_kw = ["straße","strasse","weg","gasse","platz","allee"]

    # 1) Name über Adresse
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in street_kw) and i>0:
            cand = lines[i-1].strip()
            if re.match(r"^[A-Za-zÄÖÜäöüß ]+$", cand):
                return cand

    # 2) Zeile mit Geb.datum
    for line in lines:
        if "geb.datum" in line.lower():
            p = line.split("geb.datum")[0].strip()
            if re.match(r"^[A-Za-zÄÖÜäöüß ]+$", p):
                return p

    # 3) Erste 5 Zeilen Name
    for line in lines[:5]:
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+", line):
            return line

    return None

# ─── Kombinierte Extraktion ──────────────────────────────────────────────────
def extract_customer_name(pdf_stream, blacklist:set[str]) -> str:
    # 1) Bounding-Box
    name = extract_name_by_bbox(pdf_stream, blacklist)
    if name:
        return name

    # 2) OCR + Fallback
    pdf_stream.seek(0)
    full = extract_text_with_ocr(pdf_stream)
    fb = extract_name_fallback(full)
    if fb:
        return fb

    # 3) Fallback-Timestamp
    return f"Unbekannt_{datetime.now():%Y%m%d%H%M%S}"

# ─── Dateiname sanitisieren (Spaces behalten) ────────────────────────────────
def sanitize_filename(name: str) -> str:
    # nur Sonderzeichen entfernen, Spaces bleiben
    return re.sub(r"[^\w\s]", "", name)

# ─── Streamlit UI ───────────────────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner mit Auto-Blacklist")

uploads = st.file_uploader(
    "PDFs hochladen (max. 200 MB/pro Datei)",
    type="pdf",
    accept_multiple_files=True
)

if uploads:
    # 1) globaler Header-Text aus allen PDFs
    global_texts = []
    for pdf in uploads:
        global_texts.extend(collect_header_texts(pdf))
    blacklist = set(global_texts)

    # 2) Prozessiere jedes PDF
    results, errors = [], []
    with st.spinner("Verarbeite…"):
        for pdf in uploads:
            pdf.seek(0)
            cust = extract_customer_name(pdf, blacklist)
            if cust.startswith("Unbekannt_"):
                errors.append(pdf.name)
            safe = sanitize_filename(cust)
            new = f"Vertragsauskunft {safe}.pdf"
            pdf.seek(0)
            results.append((pdf.name, new, pdf.read()))

    # Vorschau
    st.subheader("🔍 Vorschau der neuen Dateinamen")
    for orig, new, _ in results:
        st.write(f"• **{orig}** ➔ {new}")

    # ZIP
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for _, new, data in results:
            zf.writestr(new, data)
    buf.seek(0)

    st.download_button(
        "📦 ZIP herunterladen",
        buf,
        file_name="umbenannte_pdfs.zip",
        mime="application/zip"
    )

    if errors:
        st.warning("⚠️ Kein Name gefunden für:")
        for e in errors:
            st.write(f"- {e}")
