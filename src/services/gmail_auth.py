import os
import pickle
import logging
from typing import Optional
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'configuration', '.env'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GmailAuth:
    """Gmail authentication manager."""
    def __init__(self):
        """Initialize Gmail authentication."""
        self.scopes = [
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/calendar.events'
        ]
        self.token_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'configuration', 'token.json')
        self.credentials_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'configuration', 'credentials.json')
        self.creds = None

    def authenticate(self) -> Optional[Credentials]:
        """Authenticate with Gmail."""
        try:
            if os.getenv('DEVELOPMENT_MODE') == 'true':
                logger.info("Development mode: Skipping Gmail authentication")
                return None

            # Check if token exists
            if os.path.exists(self.token_path):
                with open(self.token_path, 'rb') as token:
                    self.creds = pickle.load(token)
                    if self.creds and self.creds.expired and self.creds.refresh_token:
                        self.creds.refresh(Request())
                    return self.creds
            
            logger.error("No valid credentials found")
            return None

        except Exception as e:
            logger.error(f"Failed to authenticate with Gmail: {str(e)}")
            return None

    def get_service(self):
        """Get Gmail service."""
        try:
            if os.getenv('DEVELOPMENT_MODE') == 'true':
                logger.info("Development mode: Returning None for Gmail service")
                return None

            if not self.creds:
                self.authenticate()

            service = build('gmail', 'v1', credentials=self.creds)
            logger.info("Successfully created Gmail service")
            return service

        except Exception as e:
            logger.error(f"Failed to create Gmail service: {str(e)}")
            raise

    def get_gmail_service(self):
        """Create Gmail API service."""
        try:
            credentials = self.authenticate()
            if credentials:
                return build('gmail', 'v1', credentials=credentials)
            return None
        except Exception as e:
            print(f"❌ Failed to create Gmail service: {str(e)}")
            return None

    def get_calendar_service(self):
        """Create Calendar API service."""
        try:
            # Use service account for calendar operations
            service_account_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'configuration', 'service_account.json')
            if os.path.exists(service_account_path):
                credentials = Credentials.from_service_account_file(
                    service_account_path,
                    scopes=['https://www.googleapis.com/auth/calendar.events']
                )
                return build('calendar', 'v3', credentials=credentials)
            
            logger.error("Service account file not found")
            return None
            
        except Exception as e:
            print(f"❌ Failed to create Calendar service: {str(e)}")
            return None 