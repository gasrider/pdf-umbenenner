import streamlit as st
import fitz    # PyMuPDF
import io
import re
import zipfile
from datetime import datetime

# ─── 1) Header-Blacklist generieren ──────────────────────────────────────────
def collect_header_blacklist(pdf_bytes: bytes) -> set[str]:
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

# ─── 2) Sortierte Textblöcke holen ──────────────────────────────────────────
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
        x0 = blk["bbox"][0]
        text = " ".join(
            span["text"] for line in blk["lines"] for span in line["spans"]
        ).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            blocks.append((y0, x0, text))
    return sorted(blocks, key=lambda t: t[0])

# ─── 3) Name rechts & unterhalb des Headers suchen ──────────────────────────
def extract_name_via_address(pdf_bytes: bytes, blacklist: set[str]) -> str | None:
    blocks = get_sorted_blocks(pdf_bytes)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    w, h = doc[0].rect.width, doc[0].rect.height
    doc.close()

    street_kw = ["straße","strasse","weg","gasse","platz","allee"]
    x_min = w * 0.40     # rechter Bereich
    y_min = h * 0.20     # unterhalb des Headers

    for idx, (y0, x0, text) in enumerate(blocks):
        low = text.lower()
        # nur im rechten + unteren Bereich
        if x0 < x_min or y0 < y_min:
            continue
        if any(kw in low for kw in street_kw):
            if idx > 0:
                cand = blocks[idx-1][2].strip()
                if cand in blacklist or re.search(r"\d", cand):
                    continue
                return cand
    return None

# ─── 4) Gesamten PDF-Text holen ──────────────────────────────────────────────
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
    # a) vor 'Geb.datum'
    for line in lines:
        if "geb.datum" in line.lower():
            cand = line.split("geb.datum")[0].strip()
            if re.match(r"^[A-Za-zÄÖÜäöüß ]+$", cand):
                return cand
    # b) erste 5 Zeilen 'Vorname Nachname'
    for line in lines[:5]:
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+", line):
            return line
    return None

# ─── 6) Kundenname komplett ermitteln ────────────────────────────────────────
def extract_customer_name(pdf_bytes: bytes) -> str:
    blacklist = collect_header_blacklist(pdf_bytes)

    # 1) rechts & unterhalb Header
    name = extract_name_via_address(pdf_bytes, blacklist)
    if name:
        return name

    # 2) Fallback über PDF-Text
    full = extract_pdf_text(pdf_bytes)
    fb = extract_name_fallback(full)
    if fb:
        return fb

    # 3) letzter Ausweg
    return f"Unbekannt_{datetime.now():%Y%m%d%H%M%S}"

# ─── 7) Dateinamen säubern ──────────────────────────────────────────────────
def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w\s]", "", name).strip()

# ─── 8) Streamlit UI ────────────────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner (rechts & unterhalb Header)")

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
        new_fn = f"Vertragsauskunft {safe}.pdf"
        results.append((f.name, new_fn, data))

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
        st.warning("⚠️ Kein Name gefunden in:")
        for e in errors:
            st.write(f"- {e}")
