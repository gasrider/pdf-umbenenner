import streamlit as st
import io, re, zipfile
from datetime import datetime

import fitz       # PyMuPDF
import pytesseract
from PIL import Image

# ─── OCR-Funktion ────────────────────────────────────────────────────────────
def extract_text_with_ocr(pdf_stream) -> str:
    pdf_stream.seek(0)
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

# ─── Sammle alle Header-Texte (zum Blacklisten) ─────────────────────────────
def collect_header_texts(pdf_stream):
    pdf_stream.seek(0)
    doc = fitz.open(stream=pdf_stream.read(), filetype="pdf")
    page = doc[0]
    w, h = page.rect.width, page.rect.height
    blocks = page.get_text("dict")["blocks"]
    doc.close()

    texts = []
    y_min, y_max = h * 0.10, h * 0.30
    for blk in blocks:
        y0 = blk["bbox"][1]
        if not (y_min < y0 < y_max):
            continue
        text = " ".join(
            span["text"] for line in blk["lines"] for span in line["spans"]
        ).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            texts.append(text)
    return texts

# ─── Name im gelben Rechteck (exakt) ─────────────────────────────────────────
def extract_name_in_yellow(pdf_stream, blacklist:set[str]) -> str | None:
    pdf_stream.seek(0)
    doc = fitz.open(stream=pdf_stream.read(), filetype="pdf")
    page = doc[0]
    w, h = page.rect.width, page.rect.height
    blocks = page.get_text("dict")["blocks"]
    doc.close()

    # gelb markierter Bereich:
    x_min, x_max = w * 0.45, w * 0.85
    y_min, y_max = h * 0.12, h * 0.18

    for blk in blocks:
        x0, y0, _, _ = blk["bbox"]
        if not (x_min < x0 < x_max and y_min < y0 < y_max):
            continue

        text = " ".join(
            span["text"] for line in blk["lines"] for span in line["spans"]
        ).strip()
        text = re.sub(r"\s+", " ", text)
        low = text.lower()

        # skip blacklist or digits
        if text in blacklist or re.search(r"\d", text):
            continue

        # Prüfe Person oder Firma
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
            p = line.split("geb.datum")[0].strip()
            if re.match(r"^[A-Za-zÄÖÜäöüß ]+$", p):
                return p

    for line in lines[:5]:
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+", line):
            return line

    return None

# ─── Kombinierte Extraktion ──────────────────────────────────────────────────
def extract_customer_name(pdf_stream, blacklist:set[str]) -> str:
    # 1) gelber Bereich
    name = extract_name_in_yellow(pdf_stream, blacklist)
    if name:
        return name

    # 2) OCR + Fallback
    text = extract_text_with_ocr(pdf_stream)
    fb = extract_name_fallback(text)
    if fb:
        return fb

    # 3) Zeitstempel
    return f"Unbekannt_{datetime.now():%Y%m%d%H%M%S}"

# ─── Bereinige Dateinamen ────────────────────────────────────────────────────
def sanitize_filename(name: str) -> str:
    # Sonderzeichen entfernen, Spaces beibehalten
    return re.sub(r"[^\w\s]", "", name)

# ─── Streamlit-App ──────────────────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner (exakter gelber Bereich)")

uploaded = st.file_uploader(
    "PDF-Dateien hochladen (max. 200 MB/pro Datei)",
    type="pdf",
    accept_multiple_files=True
)

if uploaded:
    # global blacklist aufbauen
    header_texts = []
    for f in uploaded:
        header_texts.extend(collect_header_texts(f))
    blacklist = set(header_texts)

    results, errors = [], []
    with st.spinner("Verarbeite…"):
        for f in uploaded:
            f.seek(0)
            cust = extract_customer_name(f, blacklist)
            if cust.startswith("Unbekannt_"):
                errors.append(f.name)
            safe = sanitize_filename(cust)
            new = f"Vertragsauskunft {safe}.pdf"
            f.seek(0)
            results.append((f.name, new, f.read()))

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
