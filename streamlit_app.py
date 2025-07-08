import streamlit as st
import fitz     # PyMuPDF
import io
import re
import zipfile
from datetime import datetime

# ─── 1) Kopfbereich-Blacklist ────────────────────────────────────────────────
def collect_header_blacklist(pdf_bytes: bytes) -> set[str]:
    """Sammelt alle Textblöcke aus den oberen 20% als Blacklist."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    cutoff = page.rect.height * 0.20
    raw = page.get_text("dict")["blocks"]
    doc.close()

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

# ─── 2) Textblöcke sortieren ─────────────────────────────────────────────────
def get_sorted_blocks(pdf_bytes: bytes):
    """Gibt eine Liste (y0, x0, text) aller Textblöcke auf Seite 1, sortiert nach y0."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    raw = page.get_text("dict")["blocks"]
    doc.close()

    blocks = []
    for blk in raw:
        if blk.get("type") != 0 or "lines" not in blk:
            continue
        y0, x0 = blk["bbox"][1], blk["bbox"][0]
        text = " ".join(
            span["text"] for line in blk["lines"] for span in line["spans"]
        ).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            blocks.append((y0, x0, text))
    return sorted(blocks, key=lambda t: t[0])

# ─── 3) Adressblock erkennen ────────────────────────────────────────────────
def is_address_block(text: str) -> bool:
    low = text.lower()
    street_kw = ["straße","strasse","weg","gasse","platz","allee"]
    if any(kw in low for kw in street_kw):
        return True
    # Postleitzahl + Stadt, z.B. "5163 Mattsee"
    if re.match(r"^\d{4}\s+[A-Za-zÄÖÜäöüß\- ]+$", text):
        return True
    return False

# ─── 4) Name-Block erkennen ──────────────────────────────────────────────────
def is_name_block(text: str) -> bool:
    """
    2–5 Tokens, jeder beginnt mit Großbuchstaben,
    erlaubt Punkte/Bindestriche (für Titel/Doppelnamen).
    """
    tokens = text.split()
    if not (2 <= len(tokens) <= 5):
        return False
    for tok in tokens:
        if not re.match(r"^[A-ZÄÖÜ][A-Za-zäöüß\.\-]+$", tok):
            return False
    return True

# ─── 5) Persönlichen Namen oberhalb der Adresse ziehen ──────────────────────
def extract_personal_name(pdf_bytes: bytes, blacklist: set[str]) -> str | None:
    blocks = get_sorted_blocks(pdf_bytes)
    for idx, (_, x0, text) in enumerate(blocks):
        if text in blacklist:
            continue
        if is_address_block(text):
            # Kandidat direkt darüber
            if idx > 0:
                cand = blocks[idx-1][2].strip()
                if cand not in blacklist and not re.search(r"\d", cand) and is_name_block(cand):
                    return cand
    return None

# ─── 6) Fallback über Gesamttext ────────────────────────────────────────────
def extract_fallback_name(pdf_bytes: bytes) -> str | None:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    full = "".join(page.get_text() + "\n" for page in doc)
    doc.close()
    lines = [l.strip() for l in full.splitlines() if l.strip()]
    # a) Zeile vor 'Geb.datum'
    for line in lines:
        if "geb.datum" in line.lower():
            cand = line.split("geb.datum")[0].strip()
            if is_name_block(cand):
                return cand
    # b) Erste 5 Zeilen
    for line in lines[:5]:
        if is_name_block(line):
            return line
    return None

# ─── 7) Komplett-Logik für Kundennamen ─────────────────────────────────────
def extract_customer_name(pdf_bytes: bytes) -> str:
    header_bl = collect_header_blacklist(pdf_bytes)

    # 1) Persönlicher Name > Adresse
    n = extract_personal_name(pdf_bytes, header_bl)
    if n:
        return n

    # 2) Heuristischer Fallback
    fb = extract_fallback_name(pdf_bytes)
    if fb:
        return fb

    # 3) letzter Ausweg
    return f"Unbekannt_{datetime.now():%Y%m%d%H%M%S}"

# ─── 8) Datei-Name bereinigen ───────────────────────────────────────────────
def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w\s]", "", name).strip()

# ─── 9) Streamlit-Oberfläche ────────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner (Bulletproof Persönlicher Name)")

uploaded = st.file_uploader(
    "PDF-Dateien hochladen (max. 200 MB/pro Datei)", 
    type="pdf", 
    accept_multiple_files=True
)

if uploaded:
    results, errors = [], []
    for f in uploaded:
        data = f.read()
        cname = extract_customer_name(data)
        if cname.startswith("Unbekannt_"):
            errors.append(f.name)
        safe = sanitize_filename(cname)
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
        st.warning("⚠️ Für diese Dateien wurde kein Name erkannt:")
        for e in errors:
            st.write(f"- {e}")
