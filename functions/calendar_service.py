import os
import json
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Globale Variablen
SCOPES = ['https://www.googleapis.com/auth/calendar']
TIMEZONE = pytz.timezone('Europe/Berlin')

def get_calendar_credentials():
    """
    Authentifiziert den Service-Account für den Google Calendar.
    Die Anmeldedaten werden entweder aus einer Umgebungsvariablen (Produktionsumgebung)
    oder aus einer lokalen JSON-Datei (Entwicklungsumgebung) geladen.
    """
    try:
        if "GOOGLE_SERVICE_ACCOUNT" in os.environ:
            # Anmeldedaten aus der Umgebungsvariablen (Heroku/Produktion)
            service_account_info = json.loads(base64.b64decode(os.environ['GOOGLE_SERVICE_ACCOUNT']))
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info, scopes=SCOPES
            )
        else:
            # Anmeldedaten aus der JSON-Datei (lokale Umgebung)
            creds_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'keys', 'solar-bot-442220-495e1d9179b6.json')
            credentials = service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)

        return credentials
    except Exception as e:
        print(f"Fehler bei der Authentifizierung: {e}")
        raise

def calculate_next_available_date(requested_weekday: int = 1, hour: int = 14, minute: int = 0) -> datetime:
    """
    Berechnet das nächste verfügbare Datum basierend auf dem gewünschten Wochentag und der Uhrzeit.
    """
    now = datetime.now(TIMEZONE)
    days_ahead = requested_weekday - now.weekday()
    if days_ahead <= 0 or (days_ahead == 0 and now.hour >= hour):
        days_ahead += 7

    next_date = now + timedelta(days=days_ahead)
    next_date = next_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

    print(f"Berechnetes Datum: {next_date.strftime('%d.%m.%Y %H:%M')}")
    return next_date

def check_availability(start_time: datetime, end_time: datetime) -> bool:
    """
    Prüft die Verfügbarkeit eines Zeitfensters im Google-Kalender.
    """
    try:
        creds = get_calendar_credentials()
        service = build('calendar', 'v3', credentials=creds)

        body = {
            "timeMin": start_time.isoformat(),
            "timeMax": end_time.isoformat(),
            "items": [{"id": "primary"}]
        }

        events_result = service.freebusy().query(body=body).execute()
        calendar_busy = events_result['calendars']['primary']['busy']
        is_available = len(calendar_busy) == 0

        print(f"Zeitslot ist {'verfügbar' if is_available else 'nicht verfügbar'}")
        return is_available
    except Exception as e:
        print(f"Fehler bei der Verfügbarkeitsprüfung: {e}")
        raise

def create_appointment(
    summary: str,
    description: str,
    start_time: datetime,
    end_time: datetime,
    email: str
) -> Dict[str, Any]:
    """
    Erstellt einen neuen Termin im Google-Kalender.
    """
    try:
        creds = get_calendar_credentials()
        service = build('calendar', 'v3', credentials=creds)

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
            # 'attendees': [{'email': email}],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 30},
                ],
            },
        }

        event = service.events().insert(calendarId='primary', body=event, sendUpdates='all').execute()

        print(f"Termin erfolgreich erstellt: {event.get('htmlLink', 'Keine URL verfügbar')}")
        return event
    except Exception as e:
        print(f"Fehler beim Erstellen des Termins: {e}")
        raise