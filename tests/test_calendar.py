from datetime import datetime, timedelta
import pytz
from pytz import timezone
from functions.calendar_service import check_availability, create_appointment

TIMEZONE = timezone('Europe/Berlin')

def test_check_availability():
    """
    Testet die Verfügbarkeit eines Zeitslots im Kalender.
    """
    start_time = datetime(2024, 11, 29, 14, 0).astimezone(pytz.timezone("Europe/Berlin"))
    end_time = start_time + timedelta(hours=1)

    print(f"Testdaten: Startzeit {start_time}, Endzeit {end_time}")

    print("Teste Verfügbarkeit...")
    is_available = check_availability(start_time, end_time)
    print(f"Ergebnis: {'Verfügbar' if is_available else 'Nicht verfügbar'}")


def test_create_appointment():
    # Test für den 26.11.2024
    start_time_26 = datetime(2024, 11, 26, 14, 0).astimezone(timezone("Europe/Berlin"))
    end_time_26 = start_time_26 + timedelta(hours=1)

    print(f"Testdaten: Startzeit {start_time_26}, Endzeit {end_time_26}")
    result_26 = create_appointment(
        summary="Testtermin 26",
        description="Dies ist ein Testtermin für den 26.11.",
        start_time=start_time_26,
        end_time=end_time_26,
        email="test@example.com"
    )
    print("Termin erstellt (26):", result_26.get("htmlLink", "Keine URL verfügbar"))

    # Test für den 24.11.2024
    start_time_24 = datetime(2024, 11, 26, 18, 0).astimezone(timezone("Europe/Berlin"))
    end_time_24 = start_time_24 + timedelta(hours=1)

    print(f"Testdaten: Startzeit {start_time_24}, Endzeit {end_time_24}")
    result_24 = create_appointment(
        summary="Testtermin 24",
        description="Dies ist ein Testtermin für den 24.11.",
        start_time=start_time_24,
        end_time=end_time_24,
        email="test@example.com"
    )
    print("Termin erstellt (24):", result_24.get("htmlLink", "Keine URL verfügbar"))
if __name__ == "__main__":
    test_check_availability()
    test_create_appointment()