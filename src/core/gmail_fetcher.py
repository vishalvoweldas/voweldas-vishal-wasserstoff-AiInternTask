import imaplib
import email
import time
import json
import logging
import os
from email.header import decode_header
from email.message import Message
from dotenv import load_dotenv
from typing import List, Dict, Optional, Any
import quopri
import base64
import chardet
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'configuration', '.env'))

# Get credentials from environment variables
EMAIL_USER = os.getenv("GMAIL_USER")
EMAIL_PASS = os.getenv("GMAIL_APP_PASSWORD")  # Use app password, NOT your real password
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
EMAILS_FILE = os.getenv("EMAILS_FILE", "emails.json")

# Validate required environment variables
if not EMAIL_USER or not EMAIL_PASS:
    if os.getenv('DEVELOPMENT_MODE', '').lower() == 'true':
        logger.warning("Using test credentials in development mode")
        EMAIL_USER = 'test@gmail.com'
        EMAIL_PASS = 'test_password'
    else:
        raise ValueError("❌ Missing Gmail credentials. Please set GMAIL_USER and GMAIL_APP_PASSWORD in .env file")

class GmailFetcher:
    def __init__(self):
        self.gmail_user = EMAIL_USER
        self.gmail_password = EMAIL_PASS
        self.imap_server = IMAP_SERVER
        self.mail = None
        self.connected = False

    def connect(self) -> bool:
        """Establish connection to Gmail IMAP server."""
        try:
            if os.getenv('DEVELOPMENT_MODE') == 'true':
                logger.info("Development mode: Simulating IMAP connection")
                return True
                
            self.mail = imaplib.IMAP4_SSL(self.imap_server)
            self.mail.login(self.gmail_user, self.gmail_password)
            self.connected = True
            logging.info("✅ Successfully connected to Gmail")
            return True
        except imaplib.IMAP4.error as e:
            logging.error(f"❌ IMAP login failed: {e}")
            return False
        except Exception as e:
            logging.error(f"❌ Connection error: {e}")
            return False

    def disconnect(self):
        """Close the IMAP connection."""
        if self.connected and self.mail:
            try:
                self.mail.logout()
                self.connected = False
                logging.info("✅ Disconnected from Gmail")
            except Exception as e:
                logging.error(f"❌ Error during logout: {e}")

    def decode_email_header(self, header: str) -> str:
        """Decode email headers that might be encoded."""
        try:
            decoded_chunks = []
            for chunk, encoding in decode_header(header):
                if isinstance(chunk, bytes):
                    if encoding:
                        decoded_chunks.append(chunk.decode(encoding))
                    else:
                        # Try to detect encoding
                        detected = chardet.detect(chunk)
                        decoded_chunks.append(chunk.decode(detected['encoding'] or 'utf-8', errors='replace'))
                else:
                    decoded_chunks.append(chunk)
            return ''.join(decoded_chunks)
        except Exception as e:
            logging.warning(f"Failed to decode header: {e}")
            return header

    def get_email_body(self, msg: Message) -> str:
        """Extract and decode email body from message."""
        body = ""
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))
                    
                    # Skip attachments
                    if "attachment" in content_disposition:
                        continue
                        
                    # Handle different content types
                    if content_type == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            try:
                                charset = part.get_content_charset() or 'utf-8'
                                body += payload.decode(charset, errors='replace')
                            except UnicodeDecodeError:
                                # Try to detect encoding
                                detected = chardet.detect(payload)
                                body += payload.decode(detected['encoding'] or 'utf-8', errors='replace')
                    elif content_type == "text/html":
                        # Skip HTML content for now, focus on plain text
                        continue
            else:
                # Handle non-multipart messages
                payload = msg.get_payload(decode=True)
                if payload:
                    try:
                        charset = msg.get_content_charset() or 'utf-8'
                        body = payload.decode(charset, errors='replace')
                    except UnicodeDecodeError:
                        detected = chardet.detect(payload)
                        body = payload.decode(detected['encoding'] or 'utf-8', errors='replace')
                        
            return body.strip()
        except Exception as e:
            logging.error(f"Error extracting email body: {e}")
            return ""

    def fetch_emails(self, limit: int = 4) -> List[Dict]:
        """Fetch emails from Gmail inbox."""
        if os.getenv('DEVELOPMENT_MODE', '').lower() == 'true':
            # In development mode, return test emails
            test_emails = [
                {
                    "from": "sender@example.com",
                    "to": "recipient@example.com",
                    "subject": "Meeting Request for Friday",
                    "date": "2024-04-05T10:00:00Z",
                    "body": "Hi,\n\nCan we schedule a meeting this Friday at 2 PM to discuss the project?\n\nBest regards,\nSender",
                    "thread_id": "thread-1"
                },
                {
                    "from": "important@example.com",
                    "to": "recipient@example.com",
                    "subject": "Security Alert: Login from new device",
                    "date": "2024-04-05T11:00:00Z",
                    "body": "We detected a login to your account from a new device. If this wasn't you, please secure your account immediately.",
                    "thread_id": "thread-2"
                }
            ]
            return test_emails[:limit]

        if not self.connected and not self.connect():
            return []

        try:
            self.mail.select("inbox")
            status, messages = self.mail.search(None, "ALL")
            
            if status != "OK":
                logging.error("Failed to search emails")
                return []
                
            email_ids = messages[0].split()
            emails = []
            
            # Process the most recent emails
            for e_id in email_ids[-limit:]:
                try:
                    status, data = self.mail.fetch(e_id, "(RFC822)")
                    if status != "OK":
                        logging.warning(f"Failed to fetch email {e_id}")
                        continue
                        
                    msg = email.message_from_bytes(data[0][1])
                    
                    # Extract and decode email components
                    subject = self.decode_email_header(msg["subject"])
                    sender = self.decode_email_header(msg["from"])
                    date = msg["date"]
                    body = self.get_email_body(msg)
                    
                    emails.append({
                        "from": sender,
                        "subject": subject,
                        "date": date,
                        "body": body
                    })
                    
                except Exception as e:
                    logging.error(f"Error processing email {e_id}: {e}")
                    continue
                    
            return emails
            
        except Exception as e:
            logging.error(f"Error fetching emails: {e}")
            return []
        finally:
            self.disconnect()

def save_emails(emails: List[Dict], file_path: str = EMAILS_FILE) -> bool:
    """Save emails to JSON file, clearing any existing data."""
    try:
        # Clear existing file by writing an empty list if it exists
        if os.path.exists(file_path):
            logging.info(f"🗑️ Clearing existing data in {file_path}")
            
        # Save new emails
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(emails, f, indent=2, ensure_ascii=False)
            
        logging.info(f"✅ Saved {len(emails)} new emails to {file_path}")
        return True
    except Exception as e:
        logging.error(f"❌ Error saving emails: {e}")
        return False

def run_every_5_minutes():
    """Main loop to fetch emails periodically."""
    fetcher = GmailFetcher()
    logging.info("⏱️ Starting Gmail fetcher service...")
    
    while True:
        try:
            emails = fetcher.fetch_emails(limit=100)
            if emails:
                # Clear and save new emails
                save_emails(emails)
            else:
                logging.warning("No emails fetched in this cycle")
                
        except Exception as e:
            logging.error(f"⚠️ Error in main loop: {e}")
            
        time.sleep(300)  # Wait 5 minutes

if __name__ == "__main__":
    run_every_5_minutes()
