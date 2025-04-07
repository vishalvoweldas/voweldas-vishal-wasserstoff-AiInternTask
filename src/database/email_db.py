import os
import json
import logging
from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path='config/.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///data/emails.db')

# Create SQLAlchemy base
Base = declarative_base()

class Email(Base):
    """Email model for database."""
    __tablename__ = 'emails'

    id = Column(String, primary_key=True)
    thread_id = Column(String)
    from_address = Column(String)
    subject = Column(String)
    date = Column(DateTime)
    body = Column(String)
    email_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EmailDatabase:
    """Database manager for emails."""
    def __init__(self):
        """Initialize database connection."""
        try:
            if os.getenv('DEVELOPMENT_MODE') == 'true':
                logger.info("Development mode: Using in-memory SQLite database")
                self.engine = create_engine('sqlite:///:memory:')
            else:
                self.engine = create_engine(DATABASE_URL)

            Base.metadata.create_all(self.engine)
            Session = sessionmaker(bind=self.engine)
            self.session = Session()
            logger.info("Successfully connected to database")

        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise

    def save_email(self, email_data: Dict[str, Any]) -> bool:
        """Save email to database."""
        try:
            if os.getenv('DEVELOPMENT_MODE') == 'true':
                logger.info("Development mode: Simulating email save")
                return True

            email = Email(
                id=email_data['id'],
                thread_id=email_data.get('thread_id', ''),
                from_address=email_data['from'],
                subject=email_data['subject'],
                date=datetime.strptime(email_data['date'], '%Y-%m-%dT%H:%M:%SZ'),
                body=email_data['body'],
                email_metadata=email_data.get('email_metadata', {})
            )

            self.session.add(email)
            self.session.commit()
            logger.info(f"Successfully saved email {email.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save email: {str(e)}")
            self.session.rollback()
            return False

    def get_email(self, email_id: str) -> Dict[str, Any]:
        """Get email from database."""
        try:
            if os.getenv('DEVELOPMENT_MODE') == 'true':
                logger.info("Development mode: Returning mock email data")
                return {
                    'id': email_id,
                    'thread_id': 'test-thread',
                    'from': 'test@example.com',
                    'subject': 'Test Email',
                    'date': '2024-04-05T10:00:00Z',
                    'body': 'This is a test email.',
                    'email_metadata': {}
                }

            email = self.session.query(Email).filter(Email.id == email_id).first()
            if not email:
                return None

            return {
                'id': email.id,
                'thread_id': email.thread_id,
                'from': email.from_address,
                'subject': email.subject,
                'date': email.date.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'body': email.body,
                'email_metadata': email.email_metadata
            }

        except Exception as e:
            logger.error(f"Failed to get email: {str(e)}")
            return None

    def get_thread_emails(self, thread_id: str) -> List[Dict[str, Any]]:
        """Get all emails in a thread."""
        try:
            if os.getenv('DEVELOPMENT_MODE') == 'true':
                logger.info("Development mode: Returning mock thread data")
                return [{
                    'id': f'test-email-{i}',
                    'thread_id': thread_id,
                    'from': 'test@example.com',
                    'subject': f'Test Email {i}',
                    'date': '2024-04-05T10:00:00Z',
                    'body': f'This is test email {i}.',
                    'email_metadata': {}
                } for i in range(3)]

            emails = self.session.query(Email).filter(Email.thread_id == thread_id).all()
            return [{
                'id': email.id,
                'thread_id': email.thread_id,
                'from': email.from_address,
                'subject': email.subject,
                'date': email.date.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'body': email.body,
                'email_metadata': email.email_metadata
            } for email in emails]

        except Exception as e:
            logger.error(f"Failed to get thread emails: {str(e)}")
            return []

    def save_reply(self, email_id: str, reply: str) -> bool:
        """Save reply to email."""
        try:
            if os.getenv('DEVELOPMENT_MODE') == 'true':
                logger.info("Development mode: Simulating reply save")
                return True

            email = self.session.query(Email).filter(Email.id == email_id).first()
            if not email:
                return False

            if 'replies' not in email.email_metadata:
                email.email_metadata['replies'] = []
            email.email_metadata['replies'].append({
                'text': reply,
                'date': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            })

            self.session.commit()
            logger.info(f"Successfully saved reply for email {email_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save reply: {str(e)}")
            self.session.rollback()
            return False

    def get_replies(self, email_id: str) -> List[str]:
        """Get all replies for an email."""
        try:
            if os.getenv('DEVELOPMENT_MODE') == 'true':
                logger.info("Development mode: Returning mock replies")
                return ["Thank you for your email. This is a test reply."]

            email = self.session.query(Email).filter(Email.id == email_id).first()
            if not email or 'replies' not in email.email_metadata:
                return []

            return [reply['text'] for reply in email.email_metadata['replies']]

        except Exception as e:
            logger.error(f"Failed to get replies: {str(e)}")
            return [] 