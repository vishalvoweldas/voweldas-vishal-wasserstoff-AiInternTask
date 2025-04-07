import json
import logging
import re
import concurrent.futures
from bs4 import BeautifulSoup
from email import message_from_string
from email.header import decode_header
import quopri
import base64
from typing import Dict, List, Optional, Union
import chardet
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class EmailCleaner:
    def __init__(self):
        # Common email patterns to clean
        self.patterns = {
            'headers': [
                r'From:.*\n',
                r'To:.*\n',
                r'Subject:.*\n',
                r'Date:.*\n',
                r'Cc:.*\n',
                r'Bcc:.*\n',
                r'Reply-To:.*\n',
                r'Return-Path:.*\n',
                r'Message-ID:.*\n',
                r'Content-Type:.*\n',
                r'Content-Transfer-Encoding:.*\n',
            ],
            'forwarded': [
                r'--\s*Forwarded message.*',
                r'Begin forwarded message:.*',
                r'Original Message.*',
            ],
            'replies': [
                r'On.*wrote:.*',
                r'On.*,.*wrote:.*',
                r'From:.*Sent:.*To:.*Subject:.*',
            ],
            'signatures': [
                r'--\s*\n.*',
                r'Best regards,.*',
                r'Regards,.*',
                r'Thanks,.*',
                r'Cheers,.*',
                r'Sincerely,.*',
            ],
            'whitespace': [
                r'\s+',
                r'\n+',
                r'\t+',
            ],
            'quoted': [
                r'>.*\n',
                r'\|.*\n',
            ],
            'attachments': [
                r'\[image:.*\]',
                r'\[cid:.*\]',
                r'<image\d+>',
            ]
        }

    def decode_email_header(self, header: str) -> str:
        """Decode email headers that might be encoded."""
        try:
            decoded_chunks = []
            for chunk, encoding in decode_header(header):
                if isinstance(chunk, bytes):
                    if encoding:
                        decoded_chunks.append(chunk.decode(encoding))
                    else:
                        decoded_chunks.append(chunk.decode('utf-8', errors='replace'))
                else:
                    decoded_chunks.append(chunk)
            return ''.join(decoded_chunks)
        except Exception as e:
            logging.warning(f"Failed to decode header: {e}")
            return header

    def clean_text(self, content: str, content_type: str = None) -> str:
        """
        Clean email content based on its type and remove common artifacts.
        
        Args:
            content: The email content to clean
            content_type: The content type of the email part
            
        Returns:
            Cleaned text content
        """
        try:
            if not content:
                return ""

            # Handle different content types
            if content_type and 'text/html' in content_type:
                soup = BeautifulSoup(content, 'html.parser')
                text = soup.get_text(separator=' ', strip=True)
            elif content_type and 'text/plain' in content_type:
                text = content
            else:
                # Try to detect content type
                if '<html' in content.lower() or '<body' in content.lower():
                    soup = BeautifulSoup(content, 'html.parser')
                    text = soup.get_text(separator=' ', strip=True)
                else:
                    text = content

            # Apply cleaning patterns
            for pattern_group in self.patterns.values():
                for pattern in pattern_group:
                    text = re.sub(pattern, ' ', text, flags=re.DOTALL | re.IGNORECASE)

            # Normalize whitespace
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()

            return text

        except Exception as e:
            logging.error(f"Error cleaning text: {e}")
            return content

    def process_email_part(self, part: message_from_string) -> str:
        """Process a single email part."""
        try:
            content_type = part.get_content_type()
            content = part.get_payload()

            # Handle different encodings
            if part.get('content-transfer-encoding') == 'quoted-printable':
                content = quopri.decodestring(content).decode('utf-8', errors='replace')
            elif part.get('content-transfer-encoding') == 'base64':
                content = base64.b64decode(content).decode('utf-8', errors='replace')

            return self.clean_text(content, content_type)
        except Exception as e:
            logging.error(f"Error processing email part: {e}")
            return ""

    def validate_cleaned_content(self, content: str) -> bool:
        """Validate the cleaned content."""
        if not content:
            return False
        
        # Check for minimum content length
        if len(content.strip()) < 10:
            return False
            
        # Check for common invalid patterns
        invalid_patterns = [
            r'^[\s\W]+$',  # Only whitespace or special characters
            r'^[0-9\s]+$',  # Only numbers and whitespace
            r'^[a-zA-Z\s]{1,3}$',  # Too short
        ]
        
        for pattern in invalid_patterns:
            if re.match(pattern, content):
                return False
                
        return True

    def extract_thread_info(self, email_data: Dict) -> Dict:
        """
        Extract thread information from email headers and content.
        
        Args:
            email_data: Raw email data dictionary
            
        Returns:
            Dict containing thread information:
            - thread_id: Unique thread identifier
            - in_reply_to: ID of the email being replied to
            - references: List of referenced email IDs
            - is_reply: Boolean indicating if this is a reply
            - subject_root: Original subject without Re:, Fwd:, etc.
            - participants: List of email addresses in the conversation
        """
        try:
            # Get email message
            email_message = message_from_string(email_data.get("body", ""))
            
            # Extract message ID
            message_id = email_message.get("Message-ID", "").strip("<>")
            if not message_id:
                message_id = str(datetime.now().timestamp())
            
            # Extract References and In-Reply-To
            references = email_message.get("References", "").split()
            references = [ref.strip("<>") for ref in references if ref]
            
            in_reply_to = email_message.get("In-Reply-To", "").strip("<>")
            
            # Extract and clean subject
            subject = email_data.get('subject', '')
            subject_root = self._clean_subject(subject)
            
            # Collect participants
            participants = set()
            
            # From
            if email_data.get('from'):
                participants.add(self._extract_email(email_data['from']))
            
            # To
            to_field = email_message.get('To', '')
            if to_field:
                for addr in to_field.split(','):
                    email = self._extract_email(addr)
                    if email:
                        participants.add(email)
            
            # CC
            cc_field = email_message.get('Cc', '')
            if cc_field:
                for addr in cc_field.split(','):
                    email = self._extract_email(addr)
                    if email:
                        participants.add(email)
            
            # Determine thread ID
            thread_id = None
            is_reply = bool(in_reply_to or references)
            
            if is_reply:
                # Use the first message in the reference chain as thread ID
                thread_id = references[0] if references else in_reply_to
            else:
                # For new threads, use the current message ID
                thread_id = message_id
            
            return {
                "message_id": message_id,
                "thread_id": thread_id,
                "in_reply_to": in_reply_to,
                "references": references,
                "is_reply": is_reply,
                "subject_root": subject_root,
                "participants": list(participants)
            }
            
        except Exception as e:
            logging.error(f"Error extracting thread info: {e}")
            return {
                "message_id": str(datetime.now().timestamp()),
                "thread_id": None,
                "in_reply_to": None,
                "references": [],
                "is_reply": False,
                "subject_root": email_data.get('subject', ''),
                "participants": []
            }

    def _clean_subject(self, subject: str) -> str:
        """Remove Re:, Fwd:, etc. from subject line"""
        prefixes = ['re:', 'fw:', 'fwd:', 'aw:', 'tr:', 'r:']
        subject = subject.lower().strip()
        
        while any(subject.startswith(prefix) for prefix in prefixes):
            for prefix in prefixes:
                if subject.startswith(prefix):
                    subject = subject[len(prefix):].strip()
        
        return subject.strip()

    def _extract_email(self, address: str) -> Optional[str]:
        """Extract email address from a string"""
        try:
            # Match email pattern
            match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', address)
            if match:
                return match.group(0).lower()
            return None
        except Exception:
            return None

    def process_email(self, email_data: Dict) -> Dict:
        """Process a single email."""
        try:
            # Extract thread information first
            thread_info = self.extract_thread_info(email_data)
            email_data.update(thread_info)
            
            # Extract email content
            raw_body = email_data.get("body", "")
            
            # Parse email message
            email_message = message_from_string(raw_body)
            
            # Process all parts of the email
            cleaned_parts = []
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_maintype() == 'text':
                        cleaned_part = self.process_email_part(part)
                        if cleaned_part:
                            cleaned_parts.append(cleaned_part)
            else:
                cleaned_parts.append(self.process_email_part(email_message))
            
            # Combine all parts
            cleaned_content = ' '.join(cleaned_parts)
            
            # Validate cleaned content
            if not self.validate_cleaned_content(cleaned_content):
                logging.warning(f"Invalid cleaned content for email from {email_data.get('from', 'unknown')}")
                cleaned_content = raw_body  # Fallback to original content
            
            # Update email data
            email_data["cleaned_summary"] = cleaned_content
            
            # Add thread markers and context
            if email_data["is_reply"]:
                context = f"[REPLY to thread: {email_data['subject_root']}] "
                if email_data.get('in_reply_to'):
                    context += f"[In reply to: {email_data['in_reply_to']}] "
                email_data["cleaned_summary"] = context + email_data['cleaned_summary']
            
            return email_data
            
        except Exception as e:
            logging.error(f"Error processing email: {e}")
            return email_data

def process_emails(input_file: str = "data/raw/emails.json", output_file: str = "data/raw/emails.json", max_workers: int = 4):
    """
    Process emails from input file, clean them, and save to output file.
    
    Args:
        input_file: Path to input JSON file
        output_file: Path to output JSON file
        max_workers: Maximum number of parallel workers
    """
    try:
        # Load emails from JSON file
        logging.info(f"Loading emails from {input_file}")
        with open(input_file, "r", encoding="utf-8") as file:
            emails = json.load(file)
            
        if not isinstance(emails, list):
            logging.error("Invalid JSON format: expected a list of emails")
            return
            
        # Initialize email cleaner
        cleaner = EmailCleaner()
        
        # Process emails in parallel
        logging.info(f"Processing {len(emails)} emails with {max_workers} workers")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            processed_emails = list(executor.map(cleaner.process_email, emails))
            
        # Save the updated data
        logging.info(f"Saving cleaned emails to {output_file}")
        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(processed_emails, file, indent=4, ensure_ascii=False)
            
        logging.info("✅ Emails have been cleaned and saved successfully!")
        
    except FileNotFoundError:
        logging.error(f"File not found: {input_file}")
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON format in {input_file}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    process_emails()
