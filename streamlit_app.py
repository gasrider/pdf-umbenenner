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
        text = page.get_text().strip()
        if text:
            full += text + "\n"
        else:
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            full += pytesseract.image_to_string(img, lang="deu") + "\n"
    doc.close()
    return full

# ─── Koordinatenbasiertes Name-Finding ───────────────────────────────────────
def extract_name_by_bbox(pdf_stream) -> str | None:
    pdf_stream.seek(0)
    doc = fitz.open(stream=pdf_stream.read(), filetype="pdf")
    page = doc[0]
    height = page.rect.height
    data = page.get_text("dict")["blocks"]
    candidates = []

    # wir suchen nur in Zeilen, deren oberer Rand (y0) zwischen
    # 10% und 30% der Seitenhöhe liegt → Header ausblenden
    y_min, y_max = height * 0.10, height * 0.30

    for block in data:
        y0 = block["bbox"][1]
        if not (y_min < y0 < y_max):
            continue
        for line in block["lines"]:
            # Text zusammenfügen und Whitespace normalisieren
            text = "".join(span["text"] for span in line["spans"])
            text = re.sub(r"\s+", " ", text).strip()

            # Muster: Vorname Nachname (2–5 Wörter, jeweils groß)
            if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+(?: [A-ZÄÖÜ][a-zäöüß]+){1,4}$", text):
                candidates.append(text)
            # Firmen können mit „GmbH“ enden
            elif re.match(r"^[A-ZÄÖÜ].+GmbH$", text):
                candidates.append(text)

    doc.close()

    return candidates[0] if candidates else None

# ─── Bisherige Fallbacks (Adresse, Geb.datum, Top-5-Zeilen) ────────────────
def extract_name_fallback(text: str) -> str | None:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    street_kw = ["straße","strasse","weg","gasse","platz","allee"]

    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in street_kw) and i>0:
            cand = lines[i-1]
            if 1<=len(cand.split())<=4 and all(c.isalpha() or c.isspace() for c in cand):
                return cand

    for line in lines:
        if "geb.datum" in line.lower():
            parts = line.split("Geb.datum")[0].strip()
            if len(parts.split())>=2:
                return parts

    for line in lines[:5]:
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+", line):
            return line

    return None

# ─── Gesamt-Extraktion ──────────────────────────────────────────────────────
def extract_customer_name(pdf_stream) -> str:
    # 1) bbox-basiert
    name = extract_name_by_bbox(pdf_stream)
    if name:
        return name

    # 2) OCR-Text + Fallback
    pdf_stream.seek(0)
    full = extract_text_with_ocr(pdf_stream)
    name = extract_name_fallback(full)
    if name:
        return name

    # 3) letzter Ausweg
    return f"Unbekannt_{datetime.now():%Y%m%d%H%M%S}"

# ─── Dateiname bereinigen ────────────────────────────────────────────────────
def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w]", "", name)

# ─── Streamlit UI ───────────────────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner (OCR + Koordinaten-Heuristik)")

uploaded = st.file_uploader(
    "PDF-Dateien hochladen (max. 200 MB/Datei)",
    type="pdf",
    accept_multiple_files=True
)

if uploaded:
    results, errors = [], []
    with st.spinner("Verarbeitung…"):
        for pdf in uploaded:
            pdf.seek(0)
            cust = extract_customer_name(pdf)
            if cust.startswith("Unbekannt_"):
                errors.append(pdf.name)
            safe = sanitize_filename(cust)
            new_name = f"Vertragsauskunft{safe}.pdf"
            pdf.seek(0)
            data = pdf.read()
            results.append((pdf.name, new_name, data))

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
        "umbenannte_pdfs.zip",
        "application/zip"
    )

    if errors:
        st.warning("⚠️ Diese Dateien konnten nicht automatisiert benannt werden:")
        for e in errors:
            st.write(f"- {e}")
