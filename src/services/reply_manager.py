import os
import json
import logging
from typing import Dict, List, Optional
from dotenv import load_dotenv
from transformers import pipeline
from src.database.email_db import EmailDatabase

# Load environment variables
load_dotenv(dotenv_path='config/.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ReplyManager:
    """Simple reply manager for development mode."""
    
    def __init__(self):
        """Initialize the reply manager."""
        self.replies_dir = "data/processed/replies"
        os.makedirs(self.replies_dir, exist_ok=True)
    
    def send_reply(self, email_data: Dict) -> None:
        """Log the reply in development mode."""
        try:
            email_id = email_data.get('id', 'unknown')
            subject = email_data.get('subject', 'No Subject')
            ai_reply = email_data.get('ai_reply', '')
            
            if not ai_reply:
                logger.warning(f"No AI reply generated for email {email_id}")
                return
                
            # In development mode, just log the reply
            logger.info(f"Would send reply to email {email_id}:")
            logger.info(f"Subject: {subject}")
            logger.info(f"Reply: {ai_reply}")
            
            # Save reply to file
            reply_file = os.path.join(self.replies_dir, f"reply_{email_id}.txt")
            with open(reply_file, 'w', encoding='utf-8') as f:
                f.write(f"Subject: {subject}\n\n{ai_reply}")
                
            logger.info(f"Reply saved to {reply_file}")
            
        except Exception as e:
            logger.error(f"Error sending reply to email {email_id}: {e}")

    def generate_reply(self, email_data: Dict) -> Optional[str]:
        """Generate a reply for the given email."""
        try:
            if os.getenv('DEVELOPMENT_MODE') == 'true':
                logger.info("Development mode: Returning mock reply")
                return "Thank you for your email. This is an automated response."

            # Analyze sentiment
            sentiment = self.sentiment_analyzer(email_data['body'])[0]
            
            # Generate appropriate reply based on sentiment
            if sentiment['label'] == 'POSITIVE':
                prompt = f"Write a friendly reply to: {email_data['subject']}\n\nDear {email_data['from']},\n"
            else:
                prompt = f"Write a professional reply to: {email_data['subject']}\n\nDear {email_data['from']},\n"
                
            reply = self.reply_generator(prompt, max_length=200, num_return_sequences=1)[0]['generated_text']
            
            # Clean up the generated reply
            reply = reply.replace(prompt, "").strip()
            
            return reply
                
        except Exception as e:
            logger.error(f"Failed to generate reply: {str(e)}")
            return None

    def save_reply(self, email_id: str, reply: str) -> bool:
        """Save the generated reply to the database."""
        try:
            self.db.save_reply(email_id, reply)
            return True
        except Exception as e:
            logger.error(f"Failed to save reply: {str(e)}")
            return False

    def get_reply_history(self, email_id: str) -> List[str]:
        """Get the history of replies for a given email."""
        try:
            return self.db.get_replies(email_id)
        except Exception as e:
            logger.error(f"Failed to get reply history: {str(e)}")
            return [] 