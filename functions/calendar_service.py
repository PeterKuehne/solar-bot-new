from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
import pickle
from datetime import datetime, timedelta
import pytz
from typing import Dict, Any, Optional
import re
from config_handler import get_google_credentials

# Absolute Pfade
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'config', 'credentials.json')
TOKEN_FILE = os.path.join(BASE_DIR, 'config', 'token.pickle')

# Google Calendar Konfiguration
SCOPES = ['https://www.googleapis.com/auth/calendar']
TIMEZONE = pytz.timezone('Europe/Berlin')


def get_calendar_credentials():
    """Google Calendar Authentifizierung für Heroku"""
    credentials_dict = get_google_credentials()
    if not credentials_dict:
        raise FileNotFoundError("Google credentials not found in environment")

    creds = None

    # Token laden, falls vorhanden
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
            print("Bestehendes Token gefunden")

    # Token prüfen und ggf. erneuern
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Access Token ist abgelaufen - erneuere mit Refresh Token...")
            creds.refresh(Request())
            print("Access Token erfolgreich erneuert")
        else:
            print("Neue Authentifizierung erforderlich (kein gültiges Refresh Token)...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            print("Neue Authentifizierung erfolgreich")

        # Token speichern
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
            print("Token in token.pickle gespeichert")

    return creds


def calculate_next_available_date(requested_weekday: int = 1, hour: int = 14, minute: int = 0) -> datetime:
    """
    Berechnet das nächste verfügbare Datum basierend auf den Anforderungen
    Args:
        requested_weekday: Tag der Woche (0=Montag, 1=Dienstag, ..., 6=Sonntag)
        hour: Gewünschte Stunde (default 14)
        minute: Gewünschte Minute (default 0)
    Returns:
        datetime: Nächstes verfügbares Datum
    """
    now = datetime.now(TIMEZONE)

    # Berechne Tage bis zum nächsten gewünschten Wochentag
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
    """
    Analysiert die Terminanfrage und extrahiert Wochentag, Stunde und Minute
    Args:
        message: Die Nachricht des Nutzers
    Returns:
        tuple: (weekday, hour, minute)
    """
    weekday_mapping = {
        'montag': 0,
        'dienstag': 1,
        'mittwoch': 2,
        'donnerstag': 3,
        'freitag': 4
    }

    # Standardwerte
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

    # Hier NICHT mehr den Wochentag überschreiben
    # weekday = 1  # Diese Zeile entfernen!

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

        # Standardbeschreibung mit korrekter UTF-8 Kodierung
        default_description = """
Solar-Beratungsgespräch

Was Sie erwartet:
- Analyse Ihres Stromverbrauchs
- Berechnung des Solarpotentials
- Individuelle Wirtschaftlichkeitsberechnung
- Fördermöglichkeiten und Finanzierung
- Konkrete nächste Schritte

Bitte bringen Sie mit:
- Aktuelle Stromrechnung
- Grundriss oder Fotos des Daches (falls vorhanden)
- Fragen und Anliegen

Bei Verhinderung bitten wir um rechtzeitige Absage.

Hinweis: Das Beratungsgespräch ist kostenlos und unverbindlich.""".encode('utf-8').decode('utf-8')

        event = {
            'summary': "Solar-Beratungsgespräch".encode('utf-8').decode('utf-8'),
            'description': default_description,
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