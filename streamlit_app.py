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

# ─── Bounding-Box Name-Detection im rechten oberen Bereich ─────────────────
def extract_name_by_bbox(pdf_stream, blacklist:set[str]) -> str | None:
    """
    Sucht nur im gelb markierten Rechteck:
      - Vertikal: 12%–28% der Seitenhöhe
      - Horizontal: 30%–90% der Seitenbreite
    Überspringt alle Texte in der globalen Blacklist.
    """
    pdf_stream.seek(0)
    doc = fitz.open(stream=pdf_stream.read(), filetype="pdf")
    page = doc[0]
    w, h = page.rect.width, page.rect.height
    blocks = page.get_text("dict")["blocks"]
    doc.close()

    # Einengung auf den gelb markierten Bereich
    y_min, y_max = h * 0.12, h * 0.28
    x_min, x_max = w * 0.30, w * 0.90

    for blk in blocks:
        x0, y0, x1, y1 = blk["bbox"]
        # muss im Rechteck liegen
        if not (x_min < x0 < x_max and y_min < y0 < y_max):
            continue

        # Text im Block sammeln
        text = " ".join(
            span["text"]
            for line in blk["lines"]
            for span in line["spans"]
        ).strip()
        text = re.sub(r"\s+", " ", text)
        low = text.lower()

        # skip blacklist oder Ziffern
        if text in blacklist or re.search(r"\d", text):
            continue

        # Privatpersonen: 2–4 Wörter, jeweils groß
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+(?: [A-ZÄÖÜ][a-zäöüß]+){1,3}$", text):
            return text
        # Firmen: endet auf GmbH
        if text.endswith("GmbH"):
            return text

    return None

# ─── Heuristischer Fallback ──────────────────────────────────────────────────
def extract_name_fallback(text: str) -> str | None:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    street_kw = ["straße","strasse","weg","gasse","platz","allee"]

    # 1) Zeile über Adresse
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in street_kw) and i>0:
            cand = lines[i-1]
            if re.match(r"^[A-Za-zÄÖÜäöüß ]+$", cand):
                return cand

    # 2) Geb.datum-Zeile
    for line in lines:
        if "geb.datum" in line.lower():
            p = line.split("geb.datum")[0].strip()
            if re.match(r"^[A-Za-zÄÖÜäöüß ]+$", p):
                return p

    # 3) Erste 5 Zeilen Vorname Nachname
    for line in lines[:5]:
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+", line):
            return line

    return None

# ─── Sammle globale Blacklist aus allen Header-Texten ───────────────────────
def collect_header_texts(pdf_stream):
    pdf_stream.seek(0)
    doc = fitz.open(stream=pdf_stream.read(), filetype="pdf")
    page = doc[0]
    w, h = page.rect.width, page.rect.height
    blocks = page.get_text("dict")["blocks"]
    doc.close()

    texts = []
    y_min, y_max = h * 0.10, h * 0.30
    x_min = 0
    x_max = w
    for blk in blocks:
        x0, y0 = blk["bbox"][0], blk["bbox"][1]
        if not (x_min < x0 < x_max and y_min < y0 < y_max):
            continue
        text = " ".join(
            span["text"] for line in blk["lines"] for span in line["spans"]
        ).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            texts.append(text)
    return texts

# ─── Gesamt-Extraktion ──────────────────────────────────────────────────────
def extract_customer_name(pdf_stream, blacklist:set[str]) -> str:
    # 1) Bounding-Box im gelb markierten Bereich
    name = extract_name_by_bbox(pdf_stream, blacklist)
    if name:
        return name

    # 2) OCR + Fallback
    pdf_stream.seek(0)
    full = extract_text_with_ocr(pdf_stream)
    fb = extract_name_fallback(full)
    if fb:
        return fb

    # 3) Letzter Ausweg
    return f"Unbekannt_{datetime.now():%Y%m%d%H%M%S}"

# ─── Dateiname bereinigen (Spaces erhalten) ─────────────────────────────────
def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w\s]", "", name)

# ─── Streamlit UI ───────────────────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner (genauer Suchbereich)")

uploads = st.file_uploader(
    "PDFs hochladen (max. 200 MB/pro Datei)",
    type="pdf",
    accept_multiple_files=True
)

if uploads:
    # 1) Blacklist aus allen Header-Blöcken
    global_texts = []
    for pdf in uploads:
        global_texts.extend(collect_header_texts(pdf))
    blacklist = set(global_texts)

    # 2) Umbenennen
    results, errors = [], []
    with st.spinner("Verarbeitung…"):
        for pdf in uploads:
            pdf.seek(0)
            cust = extract_customer_name(pdf, blacklist)
            if cust.startswith("Unbekannt_"):
                errors.append(pdf.name)
            safe = sanitize_filename(cust)
            new = f"Vertragsauskunft {safe}.pdf"
            pdf.seek(0)
            results.append((pdf.name, new, pdf.read()))

    st.subheader("🔍 Vorschau der neuen Dateinamen")
    for orig, new, _ in results:
        st.write(f"• **{orig}** ➔ {new}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for _, new, data in results:
            zf.writestr(new, data)
    buf.seek(0)

    st.download_button("📦 ZIP herunterladen", buf, "umbenannte_pdfs.zip", "application/zip")

    if errors:
        st.warning("⚠️ Kein Name gefunden für:")
        for e in errors:
            st.write(f"- {e}")
