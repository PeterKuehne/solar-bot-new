from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle
from datetime import datetime, timedelta
import pytz
from typing import Dict, Any, Optional
import json
import base64

# Absolute Pfade
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(BASE_DIR, 'config', 'token.pickle')

# Google Calendar Konfiguration
SCOPES = ['https://www.googleapis.com/auth/calendar']
TIMEZONE = pytz.timezone('Europe/Berlin')


def get_calendar_credentials():
    """Google Calendar Authentifizierung für Heroku"""
    try:
        # Versuche Token aus Umgebungsvariable zu laden
        if 'GOOGLE_TOKEN' in os.environ:
            token_data = json.loads(base64.b64decode(os.environ['GOOGLE_TOKEN']))
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
            if creds and creds.valid:
                return creds

        # Versuche Credentials aus Umgebungsvariable
        if 'GOOGLE_CREDENTIALS' in os.environ:
            client_config = json.loads(base64.b64decode(os.environ['GOOGLE_CREDENTIALS']))
            flow = InstalledAppFlow.from_client_config(
                client_config,
                SCOPES,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob'  # Für headless auth
            )
            auth_url = flow.authorization_url()[0]
            print(f"""
            Bitte besuchen Sie diese URL um den Bot zu autorisieren:
            {auth_url}

            Setzen Sie dann den erhaltenen Code als Umgebungsvariable:
            heroku config:set GOOGLE_AUTH_CODE=Ihr_Code
            """)

            if 'GOOGLE_AUTH_CODE' in os.environ:
                code = os.environ['GOOGLE_AUTH_CODE']
                flow.fetch_token(code=code)
                creds = flow.credentials

                # Speichere Token in Umgebungsvariable
                token_data = {
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': creds.scopes
                }
                token_b64 = base64.b64encode(json.dumps(token_data).encode()).decode()
                print("Speichern Sie dieses Token in der GOOGLE_TOKEN Umgebungsvariable:")
                print(token_b64)

                return creds

            raise Exception("GOOGLE_AUTH_CODE nicht gefunden")

        raise Exception("Keine Google Credentials gefunden")

    except Exception as e:
        print(f"Fehler bei Calendar Authentifizierung: {e}")
        raise


def calculate_next_available_date(requested_weekday: int = 1, hour: int = 14, minute: int = 0) -> datetime:
    """Berechnet das nächste verfügbare Datum"""
    now = datetime.now(TIMEZONE)
    days_ahead = requested_weekday - now.weekday()
    if days_ahead <= 0 or (days_ahead == 0 and now.hour >= hour):
        days_ahead += 7

    next_date = now + timedelta(days=days_ahead)
    next_date = next_date.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0
    )

    print(f"Berechnetes Datum: {next_date.strftime('%d.%m.%Y %H:%M')}")
    return next_date


def parse_appointment_request(message: str) -> tuple[int, int, int]:
    """Analysiert die Terminanfrage"""
    weekday_mapping = {
        'montag': 0,
        'dienstag': 1,
        'mittwoch': 2,
        'donnerstag': 3,
        'freitag': 4
    }

    weekday = 1  # Default ist Dienstag
    hour = 14
    minute = 0

    message = message.lower()

    # Wochentag parsen
    for day, day_num in weekday_mapping.items():
        if day in message:
            weekday = day_num
            print(f"Erkannter Wochentag: {day} ({weekday})")
            break

    # Uhrzeit parsen
    import re
    time_pattern = r'(\d{1,2})(?::(\d{2}))?\s*(?:uhr)?'
    time_match = re.search(time_pattern, message)
    if time_match:
        hour = int(time_match.group(1))
        if time_match.group(2):  # Minuten wurden angegeben
            minute = int(time_match.group(2))
        print(f"Erkannte Uhrzeit: {hour}:{minute:02d}")

    # Validierung der Geschäftszeiten
    if hour < 9 or hour > 17:
        print(f"Uhrzeit {hour}:{minute} außerhalb der Geschäftszeiten, setze auf 14:00")
        hour = 14
        minute = 0

    print(f"Finaler Termin: {['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag'][weekday]} {hour}:{minute:02d}")
    return weekday, hour, minute


def check_availability(start_time: str, end_time: str, message: str = "") -> bool:
    """Prüft die Verfügbarkeit eines Zeitslots"""
    try:
        creds = get_calendar_credentials()
        service = build('calendar', 'v3', credentials=creds)

        # Parse die gewünschte Zeit aus der Nachricht
        weekday, hour, minute = parse_appointment_request(message)
        requested_date = calculate_next_available_date(weekday, hour, minute)
        meeting_end = requested_date + timedelta(hours=1)

        print(
            f"Prüfe Verfügbarkeit für: {requested_date.strftime('%d.%m.%Y %H:%M')} - {meeting_end.strftime('%d.%m.%Y %H:%M')}")

        body = {
            "timeMin": requested_date.isoformat(),
            "timeMax": meeting_end.isoformat(),
            "items": [{"id": "primary"}]
        }

        events_result = service.freebusy().query(body=body).execute()
        calendar_busy = events_result['calendars']['primary']['busy']

        is_available = len(calendar_busy) == 0
        print(f"Zeitslot ist {'verfügbar' if is_available else 'nicht verfügbar'}")
        return is_available

    except Exception as e:
        print(f"Fehler bei der Verfügbarkeitsprüfung: {str(e)}")
        raise


def create_appointment(
        summary: str,
        description: str,
        start_time: str,
        end_time: str,
        email: str,
        message: str = ""
) -> Dict[str, Any]:
    """Erstellt einen neuen Kalendereintrag"""
    try:
        creds = get_calendar_credentials()
        service = build('calendar', 'v3', credentials=creds)

        # Parse die gewünschte Zeit aus der Nachricht
        weekday, hour, minute = parse_appointment_request(message)
        requested_date = calculate_next_available_date(weekday, hour, minute)
        meeting_end = requested_date + timedelta(hours=1)

        print(
            f"Erstelle Termin für: {requested_date.strftime('%d.%m.%Y %H:%M')} - {meeting_end.strftime('%d.%m.%Y %H:%M')}")

        event = {
            'summary': "Solar-Beratungsgespräch",
            'description': description,
            'start': {
                'dateTime': requested_date.isoformat(),
                'timeZone': 'Europe/Berlin',
            },
            'end': {
                'dateTime': meeting_end.isoformat(),
                'timeZone': 'Europe/Berlin',
            },
            'attendees': [
                {'email': email},
            ],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 30},
                ],
            },
        }

        print("Sende Kalendereintrag an Google Calendar API")
        event = service.events().insert(
            calendarId='primary',
            body=event,
            sendUpdates='all'
        ).execute()

        print(f"Termin erfolgreich erstellt: {event.get('htmlLink', 'Keine URL verfügbar')}")
        return event

    except Exception as e:
        print(f"Fehler beim Erstellen des Termins: {e}")
        raise