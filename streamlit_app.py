import streamlit as st
import fitz                             # PyMuPDF
import pytesseract
from PIL import Image
import io, re, zipfile
from datetime import datetime

# ─── 1) OCR-Crop auf gelben Bereich ──────────────────────────────────────────
def extract_via_ocr_crop(data: bytes) -> str | None:
    # PDF zu hochauflösendem Bild
    doc = fitz.open(stream=data, filetype="pdf")
    mat = fitz.Matrix(2, 2)  # 2× Skalierung
    pix = doc[0].get_pixmap(matrix=mat)
    doc.close()
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    w, h = img.size
    # gelber Bereich ca. mittig oben (30–80% Breite, 5–20% Höhe)
    left, top = int(w * 0.30), int(h * 0.05)
    right, bottom = int(w * 0.80), int(h * 0.20)
    crop = img.crop((left, top, right, bottom))

    text = pytesseract.image_to_string(crop, lang="deu")
    # suche Zeilen mit exakt 2 Tokens: Großbuchstabe am Wortanfang
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+$", line):
            return line
    return None

# ─── 2) Header-Blacklist (oberste 20 %) ─────────────────────────────────────
def collect_header_blacklist(data: bytes) -> set[str]:
    doc = fitz.open(stream=data, filetype="pdf")
    page = doc[0]
    cutoff = page.rect.height * 0.20
    raw = page.get_text("dict")["blocks"]
    doc.close()

    bl = set()
    for b in raw:
        if b.get("type") != 0 or "lines" not in b:
            continue
        y0 = b["bbox"][1]
        if y0 > cutoff:
            continue
        txt = " ".join(
            span["text"] for line in b["lines"] for span in line["spans"]
        ).strip()
        txt = re.sub(r"\s+", " ", txt)
        if txt:
            bl.add(txt)
    return bl

# ─── 3) Blöcke lesen & sortieren ─────────────────────────────────────────────
def get_sorted_blocks(data: bytes) -> list[tuple[float,float,str]]:
    doc = fitz.open(stream=data, filetype="pdf")
    raw = doc[0].get_text("dict")["blocks"]
    doc.close()

    out = []
    for b in raw:
        if b.get("type") != 0 or "lines" not in b:
            continue
        y0, x0 = b["bbox"][1], b["bbox"][0]
        txt = " ".join(
            span["text"] for line in b["lines"] for span in line["spans"]
        ).strip()
        txt = re.sub(r"\s+", " ", txt)
        if txt:
            out.append((y0, x0, txt))
    return sorted(out, key=lambda x: (x[0], x[1]))

# ─── 4) Name nach „KdNr“ ─────────────────────────────────────────────────────
def extract_after_kdnr(data: bytes, blacklist: set[str]) -> str | None:
    blocks = get_sorted_blocks(data)
    pattern = re.compile(
        r"^([A-ZÄÖÜ][A-Za-zäöüß\.\-]+(?: [A-ZÄÖÜ][A-Za-zäöüß\.\-]+){1,4})"
    )
    for i, (_, _, txt) in enumerate(blocks):
        if "kdnr" in txt.lower() and i + 1 < len(blocks):
            cand = blocks[i + 1][2]
            if cand not in blacklist:
                m = pattern.match(cand)
                if m:
                    return m.group(1)
    return None

# ─── 5) Extraktion über Adresse ──────────────────────────────────────────────
def is_address_block(txt: str) -> bool:
    low = txt.lower()
    if any(kw in low for kw in ["straße","strasse","weg","gasse","platz","allee"]):
        return True
    if re.match(r"^\d{4}\s+[A-Za-zÄÖÜäöüß\-\s]+$", txt):
        return True
    return False

def is_name_block(txt: str) -> bool:
    toks = txt.split()
    if not 2 <= len(toks) <= 5:
        return False
    return all(re.match(r"^[A-ZÄÖÜ][A-Za-zäöüß\.\-]+$", t) for t in toks)

def extract_over_address(data: bytes, blacklist: set[str]) -> str | None:
    blocks = get_sorted_blocks(data)
    for i, (_, _, txt) in enumerate(blocks):
        if txt in blacklist:
            continue
        if is_address_block(txt) and i > 0:
            cand = blocks[i - 1][2]
            if cand not in blacklist and is_name_block(cand):
                return cand
    return None

# ─── 6) Fallback „Geb.datum“ / Top-5 ─────────────────────────────────────────
def extract_fallback(data: bytes) -> str | None:
    doc = fitz.open(stream=data, filetype="pdf")
    full = "".join(page.get_text() + "\n" for page in doc)
    doc.close()
    lines = [l.strip() for l in full.splitlines() if l.strip()]

    for l in lines:
        if "geb.datum" in l.lower():
            cand = l.split("geb.datum")[0].strip()
            if is_name_block(cand):
                return cand

    for l in lines[:5]:
        if is_name_block(l):
            return l

    return None

# ─── 7) Kombinierte Logik ────────────────────────────────────────────────────
def extract_customer_name(data: bytes) -> str:
    # 1) OCR-Crop
    n = extract_via_ocr_crop(data)
    if n:
        return n

    # 2) Header-Blacklist + KdNr
    bl = collect_header_blacklist(data)
    n2 = extract_after_kdnr(data, bl)
    if n2:
        return n2

    # 3) Adresse-Heuristik
    n3 = extract_over_address(data, bl)
    if n3:
        return n3

    # 4) Fallback
    n4 = extract_fallback(data)
    if n4:
        return n4

    # 5) letzter Ausweg
    return f"Unbekannt_{datetime.now():%Y%m%d%H%M%S}"

# ─── 8) Sanitizer & UI ───────────────────────────────────────────────────────
def sanitize(name: str) -> str:
    return re.sub(r"[^\w\s]", "", name).strip()

st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner (OCR-Crop + Heuristiken)")

files = st.file_uploader("PDFs (max.200 MB)", type="pdf", accept_multiple_files=True)
if files:
    results, errs = [], []
    for f in files:
        data = f.read()
        nm = extract_customer_name(data)
        if nm.startswith("Unbekannt_"):
            errs.append(f.name)
        safe = sanitize(nm)
        new = f"Vertragsauskunft {safe}.pdf"
        results.append((f.name, new, data))

    st.subheader("🔍 Vorschau der umbenannten Dateien")
    for orig, new, _ in results:
        st.write(f"• **{orig}** ➔ {new}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for _, new, pdf in results:
            zf.writestr(new, pdf)
    buf.seek(0)
    st.download_button("📦 ZIP herunterladen", buf, "umbenannte_pdfs.zip", "application/zip")

    if errs:
        st.warning("⚠️ Für diese Dateien wurde kein Name erkannt:")
        for e in errs:
            st.write(f"- {e}")
