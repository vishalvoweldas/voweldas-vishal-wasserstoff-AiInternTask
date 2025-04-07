import logging
import os
import json
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class EmailDatabase:
    """Simple file-based database for development mode."""
    
    def __init__(self):
        """Initialize the database."""
        self.emails_file = "data/raw/emails.json"
        self.processed_file = "data/processed/processed_emails.json"
        
        # Create directories if they don't exist
        os.makedirs("data/raw", exist_ok=True)
        os.makedirs("data/processed", exist_ok=True)
        
        # Initialize empty files if they don't exist
        if not os.path.exists(self.emails_file):
            self._save_json(self.emails_file, [])
        if not os.path.exists(self.processed_file):
            self._save_json(self.processed_file, [])
    
    def _save_json(self, file_path: str, data: Any) -> None:
        """Save data to JSON file."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving to {file_path}: {e}")
    
    def _load_json(self, file_path: str) -> Any:
        """Load data from JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading from {file_path}: {e}")
            return []
    
    def save_email(self, email: Dict) -> str:
        """Save an email and return its ID."""
        emails = self._load_json(self.emails_file)
        email_id = str(len(emails) + 1)
        email['id'] = email_id
        emails.append(email)
        self._save_json(self.emails_file, emails)
        return email_id
    
    def save_processed_email(self, email_id: str, processed_data: Dict) -> None:
        """Save processed email data."""
        processed = self._load_json(self.processed_file)
        processed.append(processed_data)
        self._save_json(self.processed_file, processed)
    
    def save_calendar_event(self, email_id: str, event_data: Dict) -> None:
        """Save calendar event data."""
        # In development mode, just log the event
        logger.info(f"Calendar event saved for email {email_id}: {event_data}")
    
    def get_email(self, email_id: str) -> Optional[Dict]:
        """Get an email by ID."""
        emails = self._load_json(self.emails_file)
        for email in emails:
            if email.get('id') == email_id:
                return email
        return None 