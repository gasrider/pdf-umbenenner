import streamlit as st
import fitz                        # PyMuPDF
import pytesseract
from PIL import Image
import io, re, zipfile
from datetime import datetime

# ─── OCR auf einem Bild-Pillow-Objekt ─────────────────────────────────────────
def ocr_image(img: Image.Image) -> str:
    return pytesseract.image_to_string(img, lang="deu")

# ─── PageCrop + OCR ──────────────────────────────────────────────────────────
def ocr_crop(page, rel_box: tuple[float,float,float,float]) -> str:
    """
    Crop-Box = (x0%, y0%, x1%, y1%) in relativen Koordinaten [0..1].
    Liefert den OCR-Text aus diesem Ausschnitt.
    """
    w, h = page.rect.width, page.rect.height
    x0, y0, x1, y1 = rel_box
    rect = fitz.Rect(x0 * w, y0 * h, x1 * w, y1 * h)
    pix = page.get_pixmap(clip=rect, dpi=200)
    img = Image.open(io.BytesIO(pix.tobytes()))
    return ocr_image(img)

# ─── Name aus Text per Regex extrahieren ─────────────────────────────────────
def find_name_in_text(text: str) -> str | None:
    """
    Sucht Zeilen mit 2–4 Wörtern, jeweils Großanfang.
    Z.B. "Mag. jur. Caroline Gasser" oder "Philipp Gmachl"
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    pattern = re.compile(r"^([A-ZÄÖÜ][^\s]+\s){1,3}[A-ZÄÖÜ][^\s]+$")
    for line in lines:
        if pattern.match(line):
            return line
    return None

# ─── Gesamt-Extraktion für ein PDF ───────────────────────────────────────────
def extract_customer_name(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]

    # 1) Enge Box (gelb markiert)
    text = ocr_crop(page, (0.45, 0.12, 0.85, 0.20))
    name = find_name_in_text(text)
    if name:
        doc.close()
        return name

    # 2) Weiter Box (OCR-Fallback)
    text2 = ocr_crop(page, (0.10, 0.20, 0.90, 0.40))
    name2 = find_name_in_text(text2)
    doc.close()
    if name2:
        return name2

    # 3) Letzter Ausweg: Markiere Unbekannt mit Zeitstempel
    return f"Unbekannt_{datetime.now():%Y%m%d_%H%M%S}"

# ─── Bereinige Dateinamen (Sonderzeichen weg, Spaces behalten) ──────────────
def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w\s]", "", name).strip()

# ─── Streamlit-App ──────────────────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner (mit exaktem Crop)")

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
        st.warning("⚠️ Bei diesen Dateien kein Name gefunden:")
        for e in errors:
            st.write(f"- {e}")
