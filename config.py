"""Configuration management for Google Drive Sync."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration."""

    # Base directory
    BASE_DIR = Path(__file__).parent.absolute()

    # Google API Configuration
    SCOPES = ['https://www.googleapis.com/auth/drive']
    CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
    CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
    REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:8080/')

    # Paths
    TOKEN_FILE = BASE_DIR / 'token.json'
    CREDENTIALS_FILE = BASE_DIR / 'credentials.json'
    SYNC_STATE_FILE = BASE_DIR / '.sync_state.json'

    # Local sync folder
    LOCAL_SYNC_FOLDER = Path(os.getenv('LOCAL_SYNC_FOLDER', BASE_DIR / 'sync_folder'))

    # Google Drive folder ID (optional)
    DRIVE_FOLDER_ID = os.getenv('DRIVE_FOLDER_ID', None)

    # Sync settings
    SYNC_INTERVAL = 30  # seconds between sync checks
    MAX_RETRIES = 3
    CHUNK_SIZE = 256 * 1024  # 256 KB for file uploads

    @classmethod
    def validate(cls) -> bool:
        """Validate configuration."""
        if not cls.CLIENT_ID or not cls.CLIENT_SECRET:
            return False

        # Create sync folder if it doesn't exist
        cls.LOCAL_SYNC_FOLDER.mkdir(parents=True, exist_ok=True)

        return True

    @classmethod
    def get_client_config(cls) -> dict:
        """Get OAuth client configuration."""
        return {
            "installed": {
                "client_id": cls.CLIENT_ID,
                "client_secret": cls.CLIENT_SECRET,
                "redirect_uris": [cls.REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
