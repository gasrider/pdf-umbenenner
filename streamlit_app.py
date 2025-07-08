import streamlit as st
import fitz    # PyMuPDF
import io
import re
import zipfile
from datetime import datetime

# ─── 1) Header-Blacklist generieren ──────────────────────────────────────────
def collect_header_blacklist(pdf_bytes: bytes) -> set[str]:
    """
    Nimmt alle Text-Blöcke aus den oberen 20 % der Seite als Blacklist,
    damit wir dort nie nach Kundenname suchen.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    w, h = page.rect.width, page.rect.height
    raw = page.get_text("dict")["blocks"]
    doc.close()

    cutoff = h * 0.20
    bl = set()
    for blk in raw:
        if blk.get("type") != 0 or "lines" not in blk:
            continue
        y0 = blk["bbox"][1]
        if y0 > cutoff:
            continue
        text = " ".join(
            span["text"] for line in blk["lines"] for span in line["spans"]
        ).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            bl.add(text)
    return bl

# ─── 2) Sortierte Textblöcke ─────────────────────────────────────────────────
def get_sorted_blocks(pdf_bytes: bytes):
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

# ─── 3) Name über Adresse extrahieren (mit Blacklist-Skip) ─────────────────
def extract_name_via_address(pdf_bytes: bytes, blacklist: set[str]) -> str | None:
    blocks = get_sorted_blocks(pdf_bytes)
    street_kw = ["straße","strasse","weg","gasse","platz","allee"]

    for idx, (_, text) in enumerate(blocks):
        low = text.lower()
        if any(kw in low for kw in street_kw):
            # Kandidat direkt darüber
            if idx > 0:
                cand = blocks[idx-1][1].strip()
                # skip, wenn in blacklist oder enthält Digits
                if cand in blacklist or re.search(r"\d", cand):
                    continue
                # valid text
                return cand
    return None

# ─── 4) Gesamten PDF-Text extrahieren ────────────────────────────────────────
def extract_pdf_text(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    doc.close()
    return text

# ─── 5) Heuristischer Fallback ───────────────────────────────────────────────
def extract_name_fallback(full_text: str) -> str | None:
    lines = [l.strip() for l in full_text.splitlines() if l.strip()]
    # a) vor Geb.datum
    for line in lines:
        if "geb.datum" in line.lower():
            cand = line.split("geb.datum")[0].strip()
            if re.match(r"^[A-Za-zÄÖÜäöüß ]+$", cand):
                return cand
    # b) erste 5 Zeilen Vorname Nachname
    for line in lines[:5]:
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+", line):
            return line
    return None

# ─── 6) Komplett-Logik ───────────────────────────────────────────────────────
def extract_customer_name(pdf_bytes: bytes) -> str:
    # 1) Blacklist aus Header
    blacklist = collect_header_blacklist(pdf_bytes)

    # 2) Versuch: Name über Adresse
    name = extract_name_via_address(pdf_bytes, blacklist)
    if name:
        return name

    # 3) OCR-freier Fallback über Gesamtext
    full = extract_pdf_text(pdf_bytes)
    fb = extract_name_fallback(full)
    if fb:
        return fb

    # 4) letzter Ausweg
    return f"Unbekannt_{datetime.now():%Y%m%d%H%M%S}"

# ─── 7) Dateiname sanitisieren ──────────────────────────────────────────────
def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w\s]", "", name).strip()

# ─── 8) Streamlit-Oberfläche ─────────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner (Name über Adresse + Header-Blacklist)")

uploads = st.file_uploader(
    "PDF-Dateien hochladen (max. 200 MB/pro Datei)",
    type="pdf",
    accept_multiple_files=True
)

if uploads:
    results, errors = [], []
    for f in uploads:
        data = f.read()
        cust = extract_customer_name(data)
        if cust.startswith("Unbekannt_"):
            errors.append(f.name)
        safe = sanitize_filename(cust)
        new = f"Vertragsauskunft {safe}.pdf"
        results.append((f.name, new, data))

    st.subheader("🔍 Vorschau der umbenannten Dateien")
    for orig, new, _ in results:
        st.write(f"• **{orig}** ➔ {new}")

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
        st.warning("⚠️ Bei diesen Dateien kein Name gefunden:")
        for e in errors:
            st.write(f"- {e}")
