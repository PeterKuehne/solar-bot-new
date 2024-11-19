import os
import json
import base64


def get_google_credentials():
    """Lädt Google Credentials aus Umgebungsvariablen"""
    if 'GOOGLE_CREDENTIALS' in os.environ:
        # Decode base64-encoded credentials
        credentials_json = base64.b64decode(os.environ['GOOGLE_CREDENTIALS'])
        return json.loads(credentials_json)
    return None


def save_google_credentials():
    """Speichert Google Credentials in Umgebungsvariablen"""
    if os.path.exists('config/credentials.json'):
        with open('config/credentials.json', 'r') as f:
            credentials = f.read()
            # Encode credentials as base64
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            # Set as environment variable
            os.environ['GOOGLE_CREDENTIALS'] = encoded_credentials

            # Für Heroku
            print("Führen Sie diesen Befehl aus:")
            print(f"heroku config:set GOOGLE_CREDENTIALS={encoded_credentials}")