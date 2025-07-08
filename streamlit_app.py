import streamlit as st
import fitz       # PyMuPDF
import io, re, zipfile
from datetime import datetime

# ─── Text-Extraktion aus PDF ─────────────────────────────────────────────────
def extract_pdf_text(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    doc.close()
    return text

# ─── Name im gelben Rechteck finden (PDF-Text only) ──────────────────────────
def extract_name_in_yellow_text(pdf_bytes: bytes) -> str | None:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    w, h = page.rect.width, page.rect.height
    blocks = page.get_text("dict")["blocks"]
    doc.close()

    # gelb markierter Bereich:
    x_min, x_max = w * 0.45, w * 0.85
    y_min, y_max = h * 0.12, h * 0.20

    for blk in blocks:
        x0, y0, _, _ = blk["bbox"]
        if not (x_min < x0 < x_max and y_min < y0 < y_max):
            continue

        # Block-Text zusammenfügen
        text = " ".join(
            span["text"]
            for line in blk["lines"]
            for span in line["spans"]
        ).strip()
        text = re.sub(r"\s+", " ", text)

        # Kein reines Nummern-Gefolge
        if re.search(r"\d", text):
            continue

        # Person (2–4 Wörter) oder Firma (…GmbH)
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+(?: [A-ZÄÖÜ][a-zäöüß]+){1,3}$", text) \
        or text.endswith("GmbH"):
            return text

    return None

# ─── Heuristischer Fallback über gesamten Text ──────────────────────────────
def extract_name_fallback(text: str) -> str | None:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # 1) Suche „Geb.datum“-Zeile
    for line in lines:
        if "geb.datum" in line.lower():
            cand = line.split("geb.datum")[0].strip()
            if re.match(r"^[A-Za-zÄÖÜäöüß ]+$", cand):
                return cand
    # 2) Erste 5 Zeilen auf Vorname Nachname
    for line in lines[:5]:
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+", line):
            return line
    return None

# ─── Gesamt-Extraktion ──────────────────────────────────────────────────────
def extract_customer_name(pdf_bytes: bytes) -> str:
    # 1) Gelber Bereich via PDF-Text
    name = extract_name_in_yellow_text(pdf_bytes)
    if name:
        return name
    # 2) Fallback via gesamtem PDF-Text
    full = extract_pdf_text(pdf_bytes)
    fb = extract_name_fallback(full)
    if fb:
        return fb
    # 3) Zeitstempel
    return f"Unbekannt_{datetime.now():%Y%m%d_%H%M%S}"

# ─── Dateiname-Bereinigung ───────────────────────────────────────────────────
def sanitize_filename(name: str) -> str:
    # Sonderzeichen entfernen, Spaces erhalten
    return re.sub(r"[^\w\s]", "", name).strip()

# ─── Streamlit UI ───────────────────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner (PDF-Text only)")

files = st.file_uploader(
    "PDF-Dateien hochladen (max. 200 MB/pro Datei)",
    type="pdf",
    accept_multiple_files=True
)

if files:
    results, errors = [], []
    for f in files:
        data = f.read()
        cust = extract_customer_name(data)
        if cust.startswith("Unbekannt_"):
            errors.append(f.name)
        safe = sanitize_filename(cust)
        new_name = f"Vertragsauskunft {safe}.pdf"
        results.append((f.name, new_name, data))

    st.subheader("🔍 Vorschau der neuen Dateinamen")
    for orig, new, _ in results:
        st.write(f"• **{orig}** ➔ {new}")

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
        st.warning("⚠️ Bei folgenden Dateien kein Name gefunden:")
        for e in errors:
            st.write(f"- {e}")
