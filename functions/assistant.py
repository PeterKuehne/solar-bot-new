import os
import json
from openai import OpenAI
from prompts.solar_prompts import assistant_instructions as solar_instructions
from prompts.calendar_prompts import assistant_instructions as calendar_instructions
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv


def update_env_file(solar_id: str, calendar_id: str):
    """Aktualisiert die .env Datei mit den Assistant IDs"""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')

    # Erstelle .env wenn sie nicht existiert
    if not os.path.exists(env_path):
        open(env_path, 'a').close()

    # Lese bestehende Umgebungsvariablen
    load_dotenv(env_path)

    # Aktualisiere die Assistant IDs ohne Anführungszeichen
    with open(env_path, 'r') as file:
        lines = file.readlines()

    # Entferne bestehende Assistant ID Einträge
    lines = [line for line in lines if
             not line.startswith(('OPENAI_SOLAR_ASSISTANT_ID', 'OPENAI_CALENDAR_ASSISTANT_ID'))]

    # Füge neue IDs hinzu
    lines.extend([
        f"OPENAI_SOLAR_ASSISTANT_ID={solar_id}\n",
        f"OPENAI_CALENDAR_ASSISTANT_ID={calendar_id}\n"
    ])

    # Schreibe aktualisierte Datei
    with open(env_path, 'w') as file:
        file.writelines(lines)

    print(f"Assistant IDs wurden in {env_path} aktualisiert")


def get_next_tuesday_iso():
    """Berechnet den nächsten Dienstag und gibt das ISO-Format zurück"""
    now = datetime.now(pytz.timezone('Europe/Berlin'))
    days_ahead = 1 - now.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    next_tuesday = now + timedelta(days=days_ahead)
    next_tuesday = next_tuesday.replace(hour=14, minute=0, second=0, microsecond=0)
    return next_tuesday.isoformat()


def create_assistants(client: OpenAI) -> tuple[str, str]:
    """Erstellt oder lädt beide Assistenten (Solar und Calendar)"""
    try:
        # Solar Assistant
        solar_assistant_id = os.getenv('OPENAI_SOLAR_ASSISTANT_ID')
        if not solar_assistant_id:
            print("Creating new solar assistant...")
            solar_assistant = client.beta.assistants.create(
                name="Solar Bot",
                instructions=solar_instructions,
                model="gpt-4o-mini-2024-07-18",
                tools=[
                    {"type": "code_interpreter"},
                    {
                        "type": "function",
                        "function": {
                            "name": "solar_panel_calculations",
                            "description": "Berechnet das Solarpotential basierend auf Adresse und monatlicher Stromrechnung in Euro.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "address": {
                                        "type": "string",
                                        "description": "Deutsche Adresse für die Solarberechnung."
                                    },
                                    "monthly_bill": {
                                        "type": "integer",
                                        "description": "Monatliche Stromrechnung in Euro."
                                    }
                                },
                                "required": ["address", "monthly_bill"]
                            }
                        }
                    }
                ]
            )
            solar_assistant_id = solar_assistant.id

        # Calendar Assistant
        calendar_assistant_id = os.getenv('OPENAI_CALENDAR_ASSISTANT_ID')
        if not calendar_assistant_id:
            print("Creating new calendar assistant...")
            next_tuesday = get_next_tuesday_iso()
            end_time = (datetime.fromisoformat(next_tuesday.replace('Z', '+00:00')) + timedelta(hours=1)).isoformat()

            calendar_assistant = client.beta.assistants.create(
                name="Calendar Bot",
                instructions=calendar_instructions,
                model="gpt-4-1106-preview",
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "check_availability",
                            "description": "Prüft die Verfügbarkeit eines Zeitslots",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "start_time": {
                                        "type": "string",
                                        "description": "Startzeit im ISO Format",
                                        "default": next_tuesday
                                    },
                                    "end_time": {
                                        "type": "string",
                                        "description": "Endzeit im ISO Format",
                                        "default": end_time
                                    }
                                },
                                "required": ["start_time", "end_time"]
                            }
                        }
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "create_appointment",
                            "description": "Erstellt einen neuen Kalendereintrag",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "summary": {
                                        "type": "string",
                                        "description": "Titel des Termins",
                                        "default": "Solar-Beratungsgespräch"
                                    },
                                    "description": {
                                        "type": "string",
                                        "description": "Beschreibung des Termins"
                                    },
                                    "start_time": {
                                        "type": "string",
                                        "description": "Startzeit im ISO Format",
                                        "default": next_tuesday
                                    },
                                    "end_time": {
                                        "type": "string",
                                        "description": "Endzeit im ISO Format",
                                        "default": end_time
                                    },
                                    "email": {
                                        "type": "string",
                                        "description": "E-Mail-Adresse des Kunden"
                                    }
                                },
                                "required": ["summary", "description", "start_time", "end_time", "email"]
                            }
                        }
                    }
                ]
            )
            calendar_assistant_id = calendar_assistant.id

        print(f"""
        ================================================================
        Assistenten IDs:

        Solar Assistant ID: {solar_assistant_id}
        Calendar Assistant ID: {calendar_assistant_id}

        Die IDs wurden automatisch in der .env Datei gespeichert.
        ================================================================
        """)

        # Aktualisiere .env Datei
        update_env_file(solar_assistant_id, calendar_assistant_id)

        return solar_assistant_id, calendar_assistant_id

    except Exception as e:
        print(f"Fehler beim Erstellen/Laden der Assistenten: {e}")
        raise