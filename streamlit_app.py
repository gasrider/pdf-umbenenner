import streamlit as st
import fitz    # PyMuPDF
import io
import re
import zipfile
from datetime import datetime

# ─── PDF-Text Extraktion ─────────────────────────────────────────────────────
def extract_pdf_text(pdf_bytes: bytes) -> str:
    """
    Liest den gesamten eingebetteten Text aus dem PDF.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    all_text = ""
    for page in doc:
        all_text += page.get_text() + "\n"
    doc.close()
    return all_text

# ─── Name im gelben Bereich per PDF-Text ────────────────────────────────────
def extract_name_in_yellow_text(pdf_bytes: bytes) -> str | None:
    """
    Sucht im rechten oberen (gelb markierten) Bereich nach Namen.
    Bereich: 45–85% Breite, 12–20% Höhe.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    w, h = page.rect.width, page.rect.height
    blocks = page.get_text("dict")["blocks"]
    doc.close()

    x_min, x_max = w * 0.45, w * 0.85
    y_min, y_max = h * 0.12, h * 0.20

    for blk in blocks:
        x0, y0, _, _ = blk["bbox"]
        if not (x_min < x0 < x_max and y_min < y0 < y_max):
            continue

        # Fasse den Block-Text zusammen
        text = " ".join(
            span["text"] for line in blk["lines"] for span in line["spans"]
        ).strip()
        # Mehrfachspacings entfernen
        text = re.sub(r"\s+", " ", text)

        # Wenn Ziffern drin, skip
        if re.search(r"\d", text):
            continue

        # Privatperson (2–4 Wörter, jeder Großanfang)
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+(?: [A-ZÄÖÜ][a-zäöüß]+){1,3}$", text):
            return text
        # Firma endet auf GmbH
        if text.endswith("GmbH"):
            return text

    return None

# ─── Heuristischer Fallback auf Gesamtext ───────────────────────────────────
def extract_name_fallback(full_text: str) -> str | None:
    """
    1) Zeile oberhalb einer Adresszeile (Straßenkennung)
    2) Zeile vor 'Geb.datum'
    3) Erste 5 Zeilen 'Vorname Nachname'
    """
    lines = [l.strip() for l in full_text.splitlines() if l.strip()]
    street_kw = ["straße","strasse","weg","gasse","platz","allee"]

    # 1) Über Adresse
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in street_kw) and i > 0:
            cand = lines[i-1]
            if re.match(r"^[A-Za-zÄÖÜäöüß ]+$", cand):
                return cand

    # 2) Vor Geb.datum
    for line in lines:
        if "geb.datum" in line.lower():
            p = line.split("geb.datum")[0].strip()
            if re.match(r"^[A-Za-zÄÖÜäöüß ]+$", p):
                return p

    # 3) Erste 5 Zeilen
    for line in lines[:5]:
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+", line):
            return line

    return None

# ─── Gesamt-Extraktion ──────────────────────────────────────────────────────
def extract_customer_name(pdf_bytes: bytes) -> str:
    # 1) Gelber Bereich
    name = extract_name_in_yellow_text(pdf_bytes)
    if name:
        return name

    # 2) Fallback per Gesamtext
    full = extract_pdf_text(pdf_bytes)
    fb = extract_name_fallback(full)
    if fb:
        return fb

    # 3) Letzter Ausweg
    return f"Unbekannt_{datetime.now():%Y%m%d_%H%M%S}"

# ─── Dateiname bereinigen ────────────────────────────────────────────────────
def sanitize_filename(name: str) -> str:
    # Entfernt Sonderzeichen, belässt Buchstaben, Zahlen und Leerzeichen
    return re.sub(r"[^\w\s]", "", name).strip()

# ─── Streamlit-App ──────────────────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner (rein PDF-Text, kein OCR)")

uploaded = st.file_uploader(
    "PDF-Dateien hochladen (max. 200 MB/pro Datei)",
    type="pdf",
    accept_multiple_files=True
)

if uploaded:
    results, errors = [], []
    for f in uploaded:
        data = f.read()
        cust = extract_customer_name(data)
        if cust.startswith("Unbekannt_"):
            errors.append(f.name)
        safe = sanitize_filename(cust)
        new_name = f"Vertragsauskunft {safe}.pdf"
        results.append((f.name, new_name, data))

    st.subheader("🔍 Vorschau der umbenannten Dateien")
    for orig, new, _ in results:
        st.write(f"• **{orig}** ➔ {new}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for _, new, pdf_data in results:
            zf.writestr(new, pdf_data)
    buf.seek(0)

    st.download_button(
        "📦 ZIP herunterladen",
        buf,
        file_name="umbenannte_pdfs.zip",
        mime="application/zip"
    )

    if errors:
        st.warning("⚠️ Für diese Dateien wurde kein Name gefunden:")
        for e in errors:
            st.write(f"- {e}")
