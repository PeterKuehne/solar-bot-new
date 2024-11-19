from datetime import datetime, timedelta
from pytz import timezone
from functions.calendar_service import check_availability, create_appointment
TIMEZONE = timezone('Europe/Berlin')

def test_check_availability():
    """
    Testet die Verfügbarkeit eines Zeitslots im Kalender.
    """
    start_time = datetime(2024, 11, 21, 14, 0, tzinfo=TIMEZONE)  # 21. November 2024, 14:00 Uhr
    end_time = start_time + timedelta(hours=1)  # 21. November 2024, 15:00 Uhr

    print("Teste Verfügbarkeit...")
    is_available = check_availability(start_time, end_time)
    print(f"Ergebnis: {'Verfügbar' if is_available else 'Nicht verfügbar'}")

def test_create_appointment():
    """
    Testet die Erstellung eines Termins im Kalender.
    """
    start_time = datetime.now(TIMEZONE) + timedelta(days=1, hours=1)
    end_time = start_time + timedelta(hours=1)

    print("Erstelle Termin...")
    event = create_appointment(
        summary="Test Solar-Beratung",
        description="Dies ist ein Testtermin.",
        start_time=start_time,
        end_time=end_time,
        email="test@example.com"
    )
    print(f"Termin erstellt: {event.get('htmlLink', 'Keine URL verfügbar')}")

if __name__ == "__main__":
    test_check_availability()
    test_create_appointment()