# PDF-Umbenenner mit OCR-Unterstützung

Diese Streamlit-App liest PDF-Dateien ein, führt OCR durch (für gescannte PDFs) und extrahiert den Kundennamen. Anschließend werden die Dateien umbenannt und als ZIP-Archiv zum Download bereitgestellt.

## Installation

1. Tesseract-OCR installieren:
   - Ubuntu: `sudo apt install tesseract-ocr`
   - Windows: Lade den Installer von https://github.com/tesseract-ocr/tesseract

2. Abhängigkeiten installieren:
   ```
   pip install -r requirements.txt
   ```

3. App starten:
   ```
   streamlit run app.py
   ```
