# Anweisungen für den Solar-Assistenten
assistant_instructions = """Du bist ein hilfreicher Assistent für Solaranlagen-Beratung.
Du kannst das Solarpotential für deutsche Adressen berechnen und Kunden dabei helfen, 
die Wirtschaftlichkeit einer Solaranlage einzuschätzen."""

# Formatter für die Ausgabe der Berechnungen
formatter_prompt = """
Basierend auf Ihrer Adresse {adresse} und den monatlichen Stromkosten von {monatliche_stromkosten}€ 
hier Ihre persönliche Solaranalyse:

📊 EMPFOHLENE ANLAGENGRÖSSE
➡️ {empfohlene_anlagengroesse_kwp} kWp

💰 KOSTEN & ERSPARNIS
➡️ Geschätzte Installationskosten: {geschaetzte_installation_kosten}€
➡️ Jährliche Ersparnis: {jaehrliche_ersparnis}€
➡️ Amortisationszeit: {amortisationszeit_jahre} Jahre

⚡ LEISTUNG
➡️ Jährliche Produktion: {jaehrliche_produktion_kwh} kWh

📍 STANDORT
➡️ Breitengrad: {breite}
➡️ Längengrad: {laenge}
"""