import os
from typing import Optional
import json
import base64


class Environment:
    """Umgebungskonfiguration unabhängig vom Cloud-Provider"""

    @staticmethod
    def get_credentials_path() -> Optional[str]:
        """Holt den Pfad zu den Google Credentials"""
        # 1. Versuche lokale credentials.json
        local_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'credentials.json')
        if os.path.exists(local_path):
            return local_path

        # 2. Versuche Base64-kodierte Credentials aus Umgebungsvariablen
        if 'GOOGLE_CREDENTIALS' in os.environ:
            try:
                credentials_json = base64.b64decode(os.environ['GOOGLE_CREDENTIALS'])
                # Temporäre Datei erstellen
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as temp_file:
                    temp_file.write(credentials_json.decode())
                    return temp_file.name
            except Exception as e:
                print(f"Fehler beim Dekodieren der Credentials: {e}")
                return None

        return None

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