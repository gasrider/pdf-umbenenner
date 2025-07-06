    for i in range(len(lines) - 2):
        line1 = lines[i].strip()
        line2 = lines[i + 1].strip()
        line3 = lines[i + 2].strip()

        # Prüfe ob Zeile 2 eine Adresse ist
        if re.search(r"(straße|weg|gasse|platz|allee|ring)", line2, re.IGNORECASE) and re.match(r"\\d{4,5} ", line3):
            if re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+$", line1):
                vorname, nachname = line1.split(\" \", 1)
                return f\"Vertragsauskunft {nachname}, {vorname}.pdf\"
