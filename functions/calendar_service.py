import os
import json
import base64
from google.oauth2 import service_account
from googleapiclient.discovery import build
from typing import Dict, Any
import logging
from datetime import datetime, timedelta
import pytz
from googleapiclient.errors import HttpError
from prompts.calendar_prompts import unavailable_template, business_hours_template

# Globale Variablen
SCOPES = ['https://www.googleapis.com/auth/calendar']
TIMEZONE = pytz.timezone('Europe/Berlin')

logging.basicConfig(level=logging.INFO)


def get_calendar_credentials():
    try:
        if "GOOGLE_SERVICE_ACCOUNT" in os.environ:
            service_account_info = json.loads(base64.b64decode(os.environ['GOOGLE_SERVICE_ACCOUNT']))
            return service_account.Credentials.from_service_account_info(
                service_account_info, scopes=SCOPES
            )
        creds_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'keys',
                                  'solar-bot-442220-495e1d9179b6.json')
        return service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    except Exception as e:
        logging.error(f"Fehler bei der Authentifizierung: {e}")
        raise


def is_within_business_hours(start_time, end_time):
    # Konvertiere Strings in datetime, falls nötig
    if isinstance(start_time, str):
        start_time = datetime.fromisoformat(start_time)
    if isinstance(end_time, str):
        end_time = datetime.fromisoformat(end_time)

    business_start = start_time.replace(hour=9, minute=0, second=0, microsecond=0)
    business_end = start_time.replace(hour=17, minute=0, second=0, microsecond=0)
    lunch_start = start_time.replace(hour=12, minute=0, second=0, microsecond=0)
    lunch_end = start_time.replace(hour=13, minute=0, second=0, microsecond=0)

    return not (
        start_time < business_start or
        end_time > business_end or
        lunch_start <= start_time < lunch_end or
        lunch_start < end_time <= lunch_end or
        start_time.weekday() >= 5  # Samstag oder Sonntag
    )


def check_availability(start_time, end_time) -> dict:
    try:
        # Konvertiere Strings in datetime-Objekte, falls nötig
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time)

        # Geschäftszeiten prüfen
        if not is_within_business_hours(start_time, end_time):
            return {
                "available": False,
                "message": "Der Termin liegt außerhalb der Geschäftszeiten.",
                "busy": []
            }

        # Zeitzonenanpassung
        start_time = start_time.astimezone(TIMEZONE)
        end_time = end_time.astimezone(TIMEZONE)

        # Kalenderzugriff
        creds = get_calendar_credentials()
        service = build('calendar', 'v3', credentials=creds)

        calendar_id = 'solarbot447@gmail.com'
        body = {
            "timeMin": start_time.isoformat(),
            "timeMax": end_time.isoformat(),
            "items": [{"id": calendar_id}]
        }

        events_result = service.freebusy().query(body=body).execute()
        calendar_busy = events_result['calendars'][calendar_id]['busy']

        is_available = len(calendar_busy) == 0
        return {"available": is_available, "busy": calendar_busy}
    except Exception as e:
        print(f"Fehler bei check_availability: {e}")
        raise


def find_next_available_slots(start_time: datetime, end_time: datetime, max_attempts: int = 5) -> list:
    alternatives, increment, attempts = [], timedelta(hours=1), 0
    while len(alternatives) < max_attempts and attempts < 24:
        start_time, end_time = start_time + increment, end_time + increment
        if not is_within_business_hours(start_time, end_time):
            continue
        creds = get_calendar_credentials()
        service = build('calendar', 'v3', credentials=creds)
        calendar_id = 'solarbot447@gmail.com'
        body = {"timeMin": start_time.isoformat(), "timeMax": end_time.isoformat(), "items": [{"id": calendar_id}]}
        if not service.freebusy().query(body=body).execute()['calendars'][calendar_id]['busy']:
            alternatives.append(
                {"start_time": start_time.strftime('%d.%m.%Y %H:%M'), "end_time": end_time.strftime('%H:%M')})
        attempts += 1
    return alternatives


from datetime import datetime

def create_appointment(
        summary: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
        email: str
) -> Dict[str, Any]:
    try:
        # Konvertiere Strings in datetime-Objekte, falls nötig
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time)

        # Geschäftszeiten prüfen
        if not is_within_business_hours(start_time, end_time):
            return {"status": "failed", "message": "Der Termin liegt außerhalb der Geschäftszeiten."}

        # Verfügbarkeit prüfen
        availability = check_availability(start_time, end_time)
        if not availability["available"]:
            return {"status": "failed", "message": availability.get("message", "Zeitslot ist nicht verfügbar.")}

        # Kalenderzugriff vorbereiten
        creds = get_calendar_credentials()
        service = build('calendar', 'v3', credentials=creds)

        # Termininformationen erstellen
        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'Europe/Berlin',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'Europe/Berlin',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 30},
                ],
            },
        }

        # Termin erstellen
        created_event = service.events().insert(
            calendarId='solarbot447@gmail.com',
            body=event,
            sendUpdates='all'
        ).execute()

        return created_event

    except Exception as e:
        print(f"Fehler beim Erstellen des Termins: {e}")
        raise