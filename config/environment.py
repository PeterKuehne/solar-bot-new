import os
from typing import Optional
import json
import base64


class Environment:
    """Umgebungskonfiguration unabhängig vom Cloud-Provider"""

    @staticmethod
    def get_credentials_path() -> Optional[str]:
        """
        Holt den Pfad zu den Google Credentials.
        """
        try:
            # 1. Versuche lokale credentials.json
            local_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'keys', 'credentials.json')
            if os.path.exists(local_path):
                # Validierung der credentials.json
                with open(local_path, 'r') as file:
                    credentials = json.load(file)
                if "client_email" in credentials and "solarbot447" not in credentials["client_email"]:
                    raise ValueError(
                        "Falsche Anmeldedaten: Die client_email stimmt nicht mit dem Solarbot447-Service-Account überein."
                    )
                return local_path

            # 2. Versuche Base64-kodierte Credentials aus Umgebungsvariablen
            if 'GOOGLE_CREDENTIALS' in os.environ:
                try:
                    credentials_json = base64.b64decode(os.environ['GOOGLE_CREDENTIALS']).decode()
                    # Temporäre Datei erstellen
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as temp_file:
                        temp_file.write(credentials_json)
                        temp_file_path = temp_file.name

                    # Validierung der Umgebungsvariablen-Credentials
                    credentials = json.loads(credentials_json)
                    if "client_email" in credentials and "solarbot447" not in credentials["client_email"]:
                        raise ValueError(
                            "Falsche Anmeldedaten: Die client_email stimmt nicht mit dem Solarbot447-Service-Account überein."
                        )
                    return temp_file_path
                except Exception as e:
                    print(f"Fehler beim Dekodieren der Credentials: {e}")
                    return None

            return None
        except FileNotFoundError:
            print("Die JSON-Datei für die Anmeldedaten wurde nicht gefunden.")
            raise
        except Exception as e:
            print(f"Fehler beim Laden der Anmeldedaten: {e}")
            raise

    @staticmethod
    def get_callback_url() -> str:
        """Bestimmt die korrekte OAuth Callback URL basierend auf der Umgebung"""
        base_url = os.getenv('APP_BASE_URL', 'http://localhost:8080')
        return f"{base_url}/oauth2callback"

    @staticmethod
    def is_production() -> bool:
        """Prüft ob die App in Produktion läuft"""
        return os.getenv('ENVIRONMENT') == 'production'

    @staticmethod
    def get_port() -> int:
        """Holt den korrekten Port für die Anwendung"""
        return int(os.getenv('PORT', 8080))

    @staticmethod
    def init_app():
        """Initialisiert die Anwendungsumgebung"""
        required_vars = [
            'OPENAI_API_KEY',
            'GOOGLE_CLOUD_API_KEY',
            'AIRTABLE_API_KEY'
        ]

        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Fehlende Umgebungsvariablen: {', '.join(missing_vars)}")