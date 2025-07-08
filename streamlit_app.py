import streamlit as st
import fitz    # PyMuPDF
import io
import re
import zipfile
from datetime import datetime

# ─── 1) Sortierte Text-Blöcke aus PDF holen ─────────────────────────────────
def get_sorted_blocks(pdf_bytes: bytes):
    """
    Liest alle Text-Blöcke der ersten Seite aus und sortiert sie
    nach ihrer y0-Koordinate (von oben nach unten).
    Überspringt alle Nicht-Text-Blöcke.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    raw = page.get_text("dict")["blocks"]
    doc.close()

    blocks = []
    for blk in raw:
        # Nur Blöcke mit Text-Lines berücksichtigen
        if blk.get("type") != 0 or "lines" not in blk:
            continue
        y0 = blk["bbox"][1]
        # gesamten Text des Blocks zusammenfügen
        text = " ".join(
            span["text"]
            for line in blk["lines"]
            for span in line["spans"]
        ).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            blocks.append((y0, text))
    # sortiere nach y0
    return sorted(blocks, key=lambda t: t[0])

# ─── 2) Name direkt über der Adresse extrahieren ─────────────────────────────
def extract_name_via_address(pdf_bytes: bytes) -> str | None:
    """
    Sucht in den sortierten Blöcken nach einem Schlagwort für die Straße
    (z.B. 'Straße', 'Weg' usw.) und nimmt den Block direkt darüber als Name.
    """
    blocks = get_sorted_blocks(pdf_bytes)
    street_kw = ["straße","strasse","weg","gasse","platz","allee"]

    for idx, (_, text) in enumerate(blocks):
        low = text.lower()
        if any(kw in low for kw in street_kw):
            # vorheriger Block = Kundenname?
            if idx > 0:
                cand = blocks[idx-1][1]
                # nur Buchstaben, Leerzeichen, Punkt etc.
                if re.match(r"^[A-Za-zÄÖÜäöüß .°\-/]+$", cand):
                    return cand.strip()
    return None

# ─── 3) Heuristischer Fallback über gesamten Text ──────────────────────────
def extract_name_fallback(full_text: str) -> str | None:
    """
    a) Zeile vor 'Geb.datum'
    b) Erste fünf Zeilen nach Öffnen
    """
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

# ─── 4) PDF-Text komplett extrahieren ──────────────────────────────────────
def extract_pdf_text(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    doc.close()
    return text

# ─── 5) Gesamt-Logik: Name ermitteln ───────────────────────────────────────
def extract_customer_name(pdf_bytes: bytes) -> str:
    # 1) über Adresse
    name = extract_name_via_address(pdf_bytes)
    if name:
        return name

    # 2) Fallback
    full = extract_pdf_text(pdf_bytes)
    fb = extract_name_fallback(full)
    if fb:
        return fb

    # 3) letzter Ausweg
    return f"Unbekannt_{datetime.now():%Y%m%d%H%M%S}"

# ─── 6) Dateiname säubern ──────────────────────────────────────────────────
def sanitize_filename(name: str) -> str:
    # Sonderzeichen entfernen, Leerzeichen behalten
    return re.sub(r"[^\w\s]", "", name).strip()

# ─── 7) Streamlit-Oberfläche ───────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner (Name über Adresse)")

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
        new_fn = f"Vertragsauskunft {safe}.pdf"
        results.append((f.name, new_fn, data))

    st.subheader("🔍 Vorschau der neuen Dateinamen")
    for orig, new, _ in results:
        st.write(f"• **{orig}** ➔ {new}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for _, new, pdf_bytes in results:
            zf.writestr(new, pdf_bytes)
    buf.seek(0)

    st.download_button(
        "📦 ZIP herunterladen",
        buf,
        file_name="umbenannte_pdfs.zip",
        mime="application/zip"
    )

    if errors:
        st.warning("⚠️ Für diese Dateien kein Name gefunden:")
        for e in errors:
            st.write(f"- {e}")
