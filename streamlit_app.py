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

# ─── Koordinaten‐Heuristik: Name im oberen Bereich, ohne Ziffern, ohne Header ──
def extract_name_by_bbox(pdf_stream) -> str | None:
    pdf_stream.seek(0)
    doc = fitz.open(stream=pdf_stream.read(), filetype="pdf")
    page = doc[0]
    h = page.rect.height
    blocks = page.get_text("dict")["blocks"]
    doc.close()

    # wir schauen nur in 12–28 % der Seitenhöhe
    y_min, y_max = h * 0.12, h * 0.28

    # Header-Stichworte, danach entfernen
    header_kw = ["mondsee", "finanz", "rainerstraße", "5310", "gmbh", "kundevertragsspiegel"]
    candidates = []

    for blk in blocks:
        y0 = blk["bbox"][1]
        if not (y_min < y0 < y_max):
            continue

        # ganzen Block‐Text holen
        text = " ".join(
            span["text"] for line in blk["lines"] for span in line["spans"]
        ).strip()
        txt_l = text.lower()

        # a) überspringe Header-Stichworte
        if any(kw in txt_l for kw in header_kw):
            continue
        # b) überspringe Blöcke mit Ziffern (Adressen, Nummern)
        if re.search(r"\d", text):
            continue

        # normalize spaces
        text = re.sub(r"\s+", " ", text)

        # Privatpersonen: 2–4 Wörter, jeder mit initial groß
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+(?: [A-ZÄÖÜ][a-zäöüß]+){1,3}$", text):
            candidates.append(text)
        # Firmen: enden auf GmbH
        elif text.endswith("GmbH"):
            candidates.append(text)

    return candidates[0] if candidates else None

# ─── Heuristische Fallbacks ─────────────────────────────────────────────────
def extract_name_fallback(text: str) -> str | None:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    street_kw = ["straße","strasse","weg","gasse","platz","allee"]

    # Zeile über Adresse
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in street_kw) and i>0:
            cand = lines[i-1]
            if re.match(r"^[A-Za-zÄÖÜäöüß ]{5,40}$", cand):
                return cand

    # Zeile mit Geburtsdatum
    for line in lines:
        if "geb.datum" in line.lower():
            p = line.split("Geb.datum")[0].strip()
            if re.match(r"^[A-Za-zÄÖÜäöüß ]{5,40}$", p):
                return p

    # Erste 5 Zeilen Name
    for line in lines[:5]:
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+", line):
            return line

    return None

# ─── Gesamt-Extraktion ──────────────────────────────────────────────────────
def extract_customer_name(pdf_stream) -> str:
    # 1) Koordinaten-Heuristik
    n = extract_name_by_bbox(pdf_stream)
    if n:
        return n
    # 2) OCR + Fallback
    pdf_stream.seek(0)
    txt = extract_text_with_ocr(pdf_stream)
    n2 = extract_name_fallback(txt)
    if n2:
        return n2
    # 3) Fallback-Timestamp
    return f"Unbekannt_{datetime.now():%Y%m%d%H%M%S}"

# ─── Dateiname bereinigen ────────────────────────────────────────────────────
def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w]", "", name)

# ─── Streamlit-App ──────────────────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner mit OCR & verbessertem Header-Filter")

uploads = st.file_uploader(
    "PDFs hochladen (max. 200 MB/pro Datei)", 
    type="pdf", 
    accept_multiple_files=True
)

if uploads:
    out, errs = [], []
    with st.spinner("Bitte warten…"):
        for pdf in uploads:
            pdf.seek(0)
            name = extract_customer_name(pdf)
            if name.startswith("Unbekannt_"):
                errs.append(pdf.name)
            safe = sanitize_filename(name)
            new = f"Vertragsauskunft{safe}.pdf"
            pdf.seek(0)
            out.append((pdf.name, new, pdf.read()))

    st.subheader("🔍 Vorschau der neuen Dateinamen")
    for orig, new, _ in out:
        st.write(f"• **{orig}** ➔ {new}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for _, new, data in out:
            zf.writestr(new, data)
    buf.seek(0)

    st.download_button("📦 ZIP herunterladen", buf, "umbenannte_pdfs.zip", "application/zip")

    if errs:
        st.warning("⚠️ Kein Name gefunden für:")
        for e in errs:
            st.write(f"- {e}")
