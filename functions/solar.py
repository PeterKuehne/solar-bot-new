import json
import requests
import os
from openai import OpenAI
from dotenv import load_dotenv
from prompts.solar_prompts import assistant_instructions, formatter_prompt

# Load environment variables from .env file
load_dotenv()

GOOGLE_CLOUD_API_KEY = os.getenv('GOOGLE_CLOUD_API_KEY')
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')


# Add lead to Airtable
def create_lead(name, phone, address):
    url = "https://api.airtable.com/v0/appq9ufU7WRbeZisc/Leads"
    headers = {
        "Authorization": AIRTABLE_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "records": [{
            "fields": {
                "Name": name,
                "Phone": phone,
                "Address": address
            }
        }]
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        print("Lead created successfully.")
        return response.json()
    else:
        print(f"Failed to create lead: {response.text}")


def get_coordinates(address):
    geocoding_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GOOGLE_CLOUD_API_KEY}"
    response = requests.get(geocoding_url)
    if response.status_code == 200:
        location = response.json().get('results')[0].get('geometry').get('location')
        print(f"Coordinates for {address}: {location}")
        return location['lat'], location['lng']
    else:
        print(f"Error getting coordinates: {response.text}")


def get_solar_data_pvgis(lat, lng):
    """Get solar data from PVGIS for German addresses"""
    pvgis_url = f"https://re.jrc.ec.europa.eu/api/v5_2/PVcalc?lat={lat}&lon={lng}&peakpower=1&loss=14&outputformat=json"

    try:
        response = requests.get(pvgis_url)
        if response.status_code == 200:
            data = response.json()
            yearly_output = data['outputs']['totals']['fixed']['E_y']
            return {
                'yearly_production': yearly_output,
                'location': {'lat': lat, 'lng': lng},
                'system_size': 1
            }
        else:
            print(f"Error getting PVGIS data: {response.text}")
            return None
    except Exception as e:
        print(f"Exception in get_solar_data_pvgis: {e}")
        return None


def calculate_german_solar(monthly_bill):
    """Calculate German solar specifics"""
    STROMPREIS = 0.40
    EINSPEISEVERGUETUNG = 0.08
    INSTALLATION_KOSTEN = 1500

    yearly_consumption = (monthly_bill / STROMPREIS) * 12
    recommended_size = yearly_consumption / 1000

    return {
        'empfohlene_anlagengroesse': round(recommended_size, 2),
        'geschaetzte_kosten': round(recommended_size * INSTALLATION_KOSTEN, 2),
        'jaehrliche_ersparnis': round(yearly_consumption * (STROMPREIS - EINSPEISEVERGUETUNG), 2),
        'amortisationszeit': round(
            (recommended_size * INSTALLATION_KOSTEN) / (yearly_consumption * (STROMPREIS - EINSPEISEVERGUETUNG)), 1)
    }


def solar_panel_calculations(address, monthly_bill):
    """Hauptfunktion für Solarberechnungen in Deutschland"""
    print(f"Berechne Solarpotential für {address} mit monatlichen Kosten von {monthly_bill}€")

    try:
        lat, lng = get_coordinates(address)
        if not lat or not lng:
            return {"error": "Adresse konnte nicht gefunden werden."}

        solar_data = get_solar_data_pvgis(lat, lng)
        if not solar_data:
            return {"error": "Keine Solardaten für diesen Standort verfügbar."}

        german_calc = calculate_german_solar(float(monthly_bill))

        result = {
            "adresse": address,
            "monatliche_stromkosten": monthly_bill,
            "empfohlene_anlagengroesse_kwp": german_calc['empfohlene_anlagengroesse'],
            "geschaetzte_installation_kosten": german_calc['geschaetzte_kosten'],
            "jaehrliche_ersparnis": german_calc['jaehrliche_ersparnis'],
            "amortisationszeit_jahre": german_calc['amortisationszeit'],
            "jaehrliche_produktion_kwh": solar_data['yearly_production'],
            "standort": {
                "breite": lat,
                "laenge": lng
            }
        }

        formatted_result = formatter_prompt.format(
            adresse=result["adresse"],
            monatliche_stromkosten=result["monatliche_stromkosten"],
            empfohlene_anlagengroesse_kwp=result["empfohlene_anlagengroesse_kwp"],
            geschaetzte_installation_kosten=result["geschaetzte_installation_kosten"],
            jaehrliche_ersparnis=result["jaehrliche_ersparnis"],
            amortisationszeit_jahre=result["amortisationszeit_jahre"],
            jaehrliche_produktion_kwh=result["jaehrliche_produktion_kwh"],
            breite=result["standort"]["breite"],
            laenge=result["standort"]["laenge"]
        )

        return {
            "raw_data": result,
            "formatted_output": formatted_result
        }

    except Exception as e:
        print(f"Fehler in solar_panel_calculations: {e}")
        return {"error": f"Berechnungsfehler: {str(e)}"}