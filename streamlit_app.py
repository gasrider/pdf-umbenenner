import streamlit as st
import fitz     # PyMuPDF
import io, re, zipfile
from datetime import datetime

# ─── 1) Header-Blacklist (oberste 20 %) ─────────────────────────────────────
def collect_header_blacklist(data: bytes) -> set[str]:
    doc = fitz.open(stream=data, filetype="pdf")
    page = doc[0]
    cutoff = page.rect.height * 0.20
    raw = page.get_text("dict")["blocks"]
    doc.close()
    bl = set()
    for b in raw:
        if b.get("type")!=0 or "lines" not in b: continue
        y0 = b["bbox"][1]
        if y0>cutoff: continue
        txt = " ".join(span["text"] for line in b["lines"] for span in line["spans"])
        txt = re.sub(r"\s+"," ",txt).strip()
        if txt: bl.add(txt)
    return bl

# ─── 2) Textblöcke sortieren ─────────────────────────────────────────────────
def get_sorted_blocks(data: bytes) -> list[tuple[float,float,str]]:
    doc = fitz.open(stream=data, filetype="pdf")
    raw = doc[0].get_text("dict")["blocks"]
    doc.close()
    out=[]
    for b in raw:
        if b.get("type")!=0 or "lines" not in b: continue
        y0,x0 = b["bbox"][1], b["bbox"][0]
        txt = " ".join(span["text"] for line in b["lines"] for span in line["spans"])
        txt = re.sub(r"\s+"," ",txt).strip()
        if txt: out.append((y0,x0,txt))
    return sorted(out, key=lambda x: x[0])

# ─── 3) Name direkt nach „KdNr“ extrahieren ─────────────────────────────────
def extract_after_kdnr(data: bytes, blacklist: set[str]) -> str|None:
    blocks = get_sorted_blocks(data)
    # Regex für 2–5 Token persönliche Namen
    pattern = re.compile(r"^([A-ZÄÖÜ][A-Za-zäöüß\.\-]+(?: [A-ZÄÖÜ][A-Za-zäöüß\.\-]+){1,4}))")
    for i, (_,_,txt) in enumerate(blocks):
        if "kdnr" in txt.lower() and i+1 < len(blocks):
            cand = blocks[i+1][2]
            if cand not in blacklist:
                m = pattern.match(cand)
                if m:
                    return m.group(1)
    return None

# ─── 4) Adressblock-Erkennung ────────────────────────────────────────────────
def is_address_block(txt: str) -> bool:
    low=txt.lower()
    if any(kw in low for kw in ["straße","strasse","weg","gasse","platz","allee"]):
        return True
    if re.match(r"^\d{4}\s+[A-Za-zÄÖÜäöüß\- ]+$", txt):
        return True
    return False

def is_name_block(txt: str) -> bool:
    toks = txt.split()
    if not 2 <= len(toks) <= 5:
        return False
    return all(re.match(r"^[A-ZÄÖÜ][A-Za-zäöüß\.\-]+$", t) for t in toks)

def extract_over_address(data: bytes, blacklist: set[str]) -> str|None:
    blocks = get_sorted_blocks(data)
    for i, (_,_,txt) in enumerate(blocks):
        if txt in blacklist: continue
        if is_address_block(txt) and i>0:
            cand = blocks[i-1][2]
            if cand not in blacklist and is_name_block(cand):
                return cand
    return None

# ─── 5) Fallback über „Geb.datum“ oder Top-5 ─────────────────────────────────
def extract_fallback(data: bytes) -> str|None:
    doc = fitz.open(stream=data, filetype="pdf")
    full = "".join(p.get_text()+"\n" for p in doc)
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

# ─── 6) Gesamtabfolge ────────────────────────────────────────────────────────
def extract_customer_name(data: bytes) -> str:
    bl = collect_header_blacklist(data)
    # a) KdNr-Logik
    n = extract_after_kdnr(data, bl)
    if n: return n
    # b) Adresse oben
    n2 = extract_over_address(data, bl)
    if n2: return n2
    # c) Fallback
    n3 = extract_fallback(data)
    if n3: return n3
    # d) letzter Ausweg
    return f"Unbekannt_{datetime.now():%Y%m%d%H%M%S}"

# ─── 7) Dateinamen säubern ───────────────────────────────────────────────────
def sanitize(name: str) -> str:
    return re.sub(r"[^\w\s]", "", name).strip()

# ─── 8) Streamlit UI ─────────────────────────────────────────────────────────
st.set_page_config(page_title="PDF-Umbenenner", layout="centered")
st.title("📄 PDF-Umbenenner (KdNr+Adresse+Fallback)")

files = st.file_uploader("PDFs hochladen (max.200 MB)", type="pdf", accept_multiple_files=True)
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

    st.subheader("🔍 Vorschau")
    for o,n,_ in results:
        st.write(f"• **{o}** ➔ {n}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for _,n,p in results:
            zf.writestr(n, p)
    buf.seek(0)
    st.download_button("📦 ZIP herunterladen", buf, "umbenannte_pdfs.zip", "application/zip")

    if errs:
        st.warning("⚠️ Kein Name erkannt:")
        for e in errs:
            st.write(f"- {e}")
