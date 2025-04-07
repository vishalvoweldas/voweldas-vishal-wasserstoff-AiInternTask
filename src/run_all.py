import logging
import time
import os
import sys
import json
from datetime import datetime
from services.gmail_auth import GmailAuth
from core.gmail_fetcher import GmailFetcher
from core.email_cleaner import EmailCleaner
from core.update import (
    summarize_email, 
    classify_intent, 
    extract_request_type, 
    generate_ai_reply, 
    send_slack_message,
    create_calendar_event,
    search_web,
    process_emails_with_ai
)
from services.reply_manager import ReplyManager
from core.database import EmailDatabase
from dotenv import load_dotenv
import re
import traceback

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Load environment variables from configuration directory
env_path = os.path.join(project_root, 'configuration', '.env')
load_dotenv(env_path)

# Set development mode to false
os.environ['DEVELOPMENT_MODE'] = 'false'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_meeting_details(email_body):
    """Extract meeting date and time from email body."""
    try:
        # Common date patterns
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
            r'(\d{2}/\d{2}/\d{4})',  # DD/MM/YYYY
            r'(\d{2}-\d{2}-\d{4})'   # DD-MM-YYYY
        ]
        
        # Common time patterns
        time_patterns = [
            r'(\d{1,2}:\d{2}\s*[AP]M)',  # 12-hour format
            r'(\d{2}:\d{2})'              # 24-hour format
        ]
        
        # Search for date and time
        date = None
        time = None
        
        for pattern in date_patterns:
            match = re.search(pattern, email_body)
            if match:
                date = match.group(1)
                break
                
        for pattern in time_patterns:
            match = re.search(pattern, email_body)
            if match:
                time = match.group(1)
                break
                
        if date and time:
            # Convert time to 24-hour format if needed
            if 'AM' in time or 'PM' in time:
                time_obj = datetime.strptime(time, '%I:%M %p')
                time = time_obj.strftime('%H:%M')
                
            # Create datetime object
            meeting_time = datetime.strptime(f"{date} {time}", '%Y-%m-%d %H:%M')
            return meeting_time
            
        return None
        
    except Exception as e:
        logger.error(f"⚠️ Error extracting meeting details: {str(e)}")
        return None

def fetch_new_emails():
    """Fetch new emails from Gmail."""
    gmail_fetcher = GmailFetcher()
    emails = gmail_fetcher.fetch_emails()
    if not emails:
        logger.info("ℹ️ No new emails to process")
        return []
    return emails

def clean_emails(emails):
    """Clean and process raw emails."""
    email_cleaner = EmailCleaner()
    cleaned_emails = []
    for email in emails:
        cleaned_email = email_cleaner.process_email(email)
        if cleaned_email:
            cleaned_emails.append(cleaned_email)
    
    if not cleaned_emails:
        logger.error("❌ No cleaned emails to process")
        return []
    return cleaned_emails

def process_emails_with_ai(emails):
    """Process emails using AI features."""
    processed_count = 0
    processed_emails = []  # List to store processed emails
    
    print("\n🔄 Processing emails with AI features...")
    
    for email in emails:
        try:
            print(f"\n📧 Processing email: {email['subject']}")
            
            # Generate summary
            print("🔍 Analyzing email body...")
            summary = summarize_email(email['body'])
            
            # Classify intent and request type
            print("🎯 Detecting intent...")
            intent = classify_intent(email['body'])
            request_type = extract_request_type(email['body'])
            print(f"📝 Intent: {intent}, Request Type: {request_type}")
            
            # Generate AI reply
            print("🧠 Generating reply...")
            reply = generate_ai_reply(email['subject'], email['body'], email['from'])
            
            # Send Slack notification
            slack_message = f":envelope_with_arrow: *New Important Email*\n\n*Subject*: {email['subject']}\n*Body*: {summary}"
            send_slack_message(slack_message)
            
            # Check for event/meeting intent and create calendar event
            calendar_event_created = False
            if (intent in ["Event", "Meeting", "Appointment"] or 
                request_type in ["Calendar Event", "Meeting Request", "Appointment Request"]):
                print("🔍 Detected meeting intent, searching for date and time...")
                meeting_time = extract_meeting_details(email['body'])
                if meeting_time:
                    print(f"📅 Found meeting time: {meeting_time}")
                    event_data = {
                        'subject': email['subject'],
                        'body': email['body'],
                        'meeting_time': meeting_time
                    }
                    if create_calendar_event(event_data):
                        logger.info(f"✅ Calendar event created for {meeting_time}")
                        calendar_event_created = True
                        # Add event link to the reply
                        reply += f"\n\nI've added this event to your calendar for {meeting_time.strftime('%B %d, %Y at %I:%M %p')}."
                    else:
                        logger.warning("⚠️ Failed to create calendar event")
                        reply += "\n\nNote: I couldn't add this event to your calendar automatically. Please add it manually."
                else:
                    print("⚠️ No meeting time found in the email")
            
            # Add to processed emails
            processed_emails.append({
                'from': email['from'],
                'subject': email['subject'],
                'summary': summary,
                'intent': intent,
                'request_type': request_type,
                'ai_reply': reply,
                'calendar_event_created': calendar_event_created,
                'processed_at': datetime.now().isoformat()
            })
            
            processed_count += 1
            print(f"✅ Email processed successfully ({processed_count}/{len(emails)})")
            
        except Exception as e:
            logger.error(f"⚠️ Error processing email: {str(e)}")
            continue
    
    return processed_emails  # Return the list of processed emails instead of count

def process_emails(emails):
    """Process emails through the AI pipeline."""
    try:
        print("\n🔄 Processing emails with AI features...")
        processed_emails = process_emails_with_ai(emails)
        
        # Save processed emails
        if processed_emails and len(processed_emails) > 0:
            # Create data/processed directory if it doesn't exist
            output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'processed')
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, 'processed_emails.json')
            
            print(f"\n📂 Saving {len(processed_emails)} processed emails to: {output_file}")
            
            try:
                # Delete existing file if it exists
                if os.path.exists(output_file):
                    print("🗑️ Deleting existing processed emails file...")
                    os.remove(output_file)
                    print("✅ Existing file deleted successfully")
                
                # Save new emails
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(processed_emails, f, indent=2, ensure_ascii=False)
                
                print(f"💾 Successfully saved {len(processed_emails)} new emails to '{output_file}'")
                logger.info(f"✅ Successfully processed and saved {len(processed_emails)} new emails")
                
            except Exception as e:
                logger.error(f"⚠️ Error saving processed emails: {str(e)}")
                traceback.print_exc()
        
        return processed_emails
        
    except Exception as e:
        logger.error(f"⚠️ Error in process_emails: {str(e)}")
        traceback.print_exc()
        return []

def main():
    """Main function to run the email processing pipeline."""
    try:
        # Initialize logging
        logger.info("🔄 Starting email pipeline service (running every 5 minutes)...")
        logger.info("\n🛑 To stop the program:")
        logger.info("1. Press Ctrl+C")
        logger.info("2. Or run 'python -c \"open('stop.txt', 'w').close()\"' in another terminal")
        
        while True:
            try:
                start_time = time.time()
                
                # Step 1: Fetch new emails
                logger.info("🔄 Step 1: Fetching new emails...")
                new_emails = fetch_new_emails()
                
                # Step 2: Clean emails
                logger.info("🔄 Step 2: Cleaning emails...")
                cleaned_emails = clean_emails(new_emails)
                logger.info("✅ Emails cleaned successfully")
                
                # Step 3: Process emails
                logger.info("🔄 Step 3: Processing emails...")
                processed_emails = process_emails(cleaned_emails)
                
                if processed_emails:
                    logger.info(f"✅ Email pipeline completed successfully in {time.time() - start_time:.2f} seconds!")
                
                # Wait for 5 minutes before next run
                logger.info("💤 Cycle 1 completed. Waiting 5 minutes before next run...")
                time.sleep(300)  # 5 minutes
                
            except Exception as e:
                logger.error(f"❌ Error in main loop: {str(e)}")
                traceback.print_exc()
                time.sleep(60)  # Wait 1 minute before retrying
                
            # Check for stop signal
            if os.path.exists('stop.txt'):
                logger.info("🛑 Stop signal received. Cleaning up...")
                os.remove('stop.txt')
                break
                
    except KeyboardInterrupt:
        logger.info("👋 Program terminated by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main() 