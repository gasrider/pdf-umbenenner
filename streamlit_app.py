import streamlit as st
import fitz     # PyMuPDF
import io
import re
import zipfile
from datetime import datetime

# ─── 1) Textblöcke sortieren ───────────────────────────────────────────────
def get_sorted_blocks(pdf_bytes: bytes):
    """
    Liefert eine Liste (y0, text) aller Textblöcke auf Seite 1,
    sortiert von oben (kleines y0) nach unten (großes y0).
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    raw = page.get_text("dict")["blocks"]
    doc.close()

    blocks = []
    for blk in raw:
        if blk.get("type") != 0 or "lines" not in blk:
            continue
        y0 = blk["bbox"][1]
        text = " ".join(
            span["text"] for line in blk["lines"] for span in line["spans"]
        ).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            blocks.append((y0, text))
    return sorted(blocks, key=lambda t: t[0])

# ─── 2) Persönlichen Namen oberhalb der Adresse finden ──────────────────────
def extract_personal_name(pdf_bytes: bytes) -> str | None:
    """
    Sucht in den sortierten Blöcken nach einer Adresszeile (enthält Straße o.ä.).
    Gibt den Block direkt darüber zurück, wenn er genau aus zwei Wörtern besteht
    und beide mit Großbuchstaben beginnen.
    """
    blocks = get_sorted_blocks(pdf_bytes)
    street_keywords = ["straße", "strasse", "weg", "gasse", "platz", "allee"]
    name_pattern = re.compile(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+$")

    for idx, (_, text) in enumerate(blocks):
        low = text.lower()
        if any(kw in low for kw in street_keywords):
            if idx > 0:
                cand = blocks[idx - 1][1].strip()
                if name_pattern.match(cand):
                    return cand
    return None

# ─── 3) Fallback: Name vor „Geb.datum“ oder in Top-5-Zeilen ──────────────
def extract_fallback_name(pdf_bytes: bytes) -> str | None:
    full_text = ""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        full_text += page.get_text() + "\n"
    doc.close()

    lines = [l.strip() for l in full_text.splitlines() if l.strip()]
    name_pattern = re.compile(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+$")

    # a) Zeile vor „Geb.datum“
    for line in lines:
        if "geb.datum" in line.lower():
            cand = line.split("geb.datum")[0].strip()
            if name_pattern.match(cand):
                return cand

    # b) Erste fünf Zeilen
    for line in lines[:5]:
        if name_pattern.match(line):
            return line

    return None

# ─── 4) Vollständige Extraktion ─────────────────────────────────────────────
def extract_customer_name(pdf_bytes: bytes) -> str:
    # 1) persönlicher Name oberhalb Adresse
    name = extract_personal_name(pdf_bytes)
    if name:
        return name

    # 2) Fallback
    fb = extract_fallback_name(pdf_bytes)
    if fb:
        return fb

    # 3) letzter Ausweg
    return f"Unbekannt_{datetime.now():%Y%m%d_%H%M%S}"

# ─── 5) Dateinamen bereinigen ───────────────────────────────────────────────
def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w\s]", "", name).strip()

# ─── 6) Streamlit-App ───────────────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner (nur Vorname Nachname)")

uploaded_files = st.file_uploader(
    "PDF-Dateien hochladen (max. 200 MB/pro Datei)", 
    type="pdf", 
    accept_multiple_files=True
)

if uploaded_files:
    results = []
    errors = []

    for f in uploaded_files:
        data = f.read()
        cname = extract_customer_name(data)
        if cname.startswith("Unbekannt_"):
            errors.append(f.name)
        safe = sanitize_filename(cname)
        new_name = f"Vertragsauskunft {safe}.pdf"
        results.append((f.name, new_name, data))

    st.subheader("🔍 Vorschau der neuen Dateinamen")
    for orig, new, _ in results:
        st.write(f"• **{orig}** ➔ {new}")

    # ZIP-Paket erzeugen
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for _, new, pdfdata in results:
            zf.writestr(new, pdfdata)
    buf.seek(0)

    st.download_button(
        "📦 ZIP herunterladen",
        buf,
        file_name="umbenannte_pdfs.zip",
        mime="application/zip"
    )

    if errors:
        st.warning("⚠️ Für diese Dateien wurde kein Vorname+Nachname erkannt:")
        for e in errors:
            st.write(f"- {e}")
