import os
import json
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import tensorflow as tf
from huggingface_hub import login
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from typing import List, Dict, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.auth import jwt
from datetime import datetime, timedelta
import pytz
import re
from google.oauth2.credentials import Credentials
import time

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ✅ Secure API Keys & Tokens
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "all-new-workspace")  # Set default to all-new-workspace
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")

# Validate required environment variables
if not all([HUGGINGFACE_TOKEN, SLACK_BOT_TOKEN, GOOGLE_API_KEY, SEARCH_ENGINE_ID, SLACK_CHANNEL]):
    if os.getenv('DEVELOPMENT_MODE') == 'true':
        logger.warning("Using test API keys in development mode")
        HUGGINGFACE_TOKEN = 'test_token'
        SLACK_BOT_TOKEN = 'xoxb-test-token'
        GOOGLE_API_KEY = 'test_api_key'
        SEARCH_ENGINE_ID = 'test_search_id'
        SLACK_CHANNEL = 'all-new-workspace'  # Set test channel to all-new-workspace
    else:
        raise ValueError("ERROR: Missing required API keys or tokens. Check your .env file.")

# Check if AI features are enabled
AI_ENABLED = all(token != "disabled" for token in [HUGGINGFACE_TOKEN, SLACK_BOT_TOKEN, GOOGLE_API_KEY, SEARCH_ENGINE_ID])

if AI_ENABLED:
    # ✅ Ensure required keys exist
    if not HUGGINGFACE_TOKEN or not SLACK_BOT_TOKEN or not GOOGLE_API_KEY or not SEARCH_ENGINE_ID:
        if os.getenv('DEVELOPMENT_MODE', '').lower() == 'true':
            logger.warning("Using test API keys in development mode")
            # Set test values for development mode
            HUGGINGFACE_TOKEN = "test_token"
            SLACK_BOT_TOKEN = "test_slack_token"
            GOOGLE_API_KEY = "test_api_key"
            SEARCH_ENGINE_ID = "test_search_id"
        else:
            raise ValueError("❌ ERROR: Missing required API keys or tokens. Check your .env file.")

    # ✅ Authenticate with Hugging Face
    if os.getenv('DEVELOPMENT_MODE', '').lower() != 'true':
        login(token=HUGGINGFACE_TOKEN)
    else:
        logger.info("Development mode: Skipping Hugging Face authentication")

    # ✅ Initialize Slack Client
    client = WebClient(token=SLACK_BOT_TOKEN)

    # ✅ Suppress TensorFlow warnings
    logging.getLogger("tensorflow").setLevel(logging.ERROR)

    # ✅ Load AI Models
    print("🔄 Loading AI models...")

    # Use CPU in development mode to avoid GPU requirements
    device = -1 if os.getenv('DEVELOPMENT_MODE', '').lower() == 'true' else 0
    print(f"Device set to use {'cpu' if device == -1 else 'gpu'}")

    summarizer = pipeline("summarization", model="t5-small", device=device)
    classifier = pipeline("zero-shot-classification", model="cross-encoder/nli-distilroberta-base", device=device)

    # ✅ GPT-2 Model for replies
    gpt2_tokenizer = AutoTokenizer.from_pretrained("gpt2")
    gpt2_model = AutoModelForCausalLM.from_pretrained("gpt2")
    gpt2_tokenizer.pad_token = gpt2_tokenizer.eos_token  # Fix pad token issue

    print("✅ Models loaded successfully!")
else:
    print("⚠️ AI features are disabled. Running in basic mode.")

# ✅ Function to send Slack messages
def send_slack_message(message):
    """Send message to Slack."""
    try:
        # Get Slack token from environment variables
        slack_token = os.getenv('SLACK_BOT_TOKEN')
        if not slack_token:
            logger.error("❌ Slack bot token not found in environment variables")
            return False
        
        # Initialize Slack client
        client = WebClient(token=slack_token)
        
        # Send message
        response = client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=message,
            mrkdwn=True
        )
        
        if response['ok']:
            logger.info("✅ Slack message sent: %s", message)
            return True
        else:
            logger.error("❌ Failed to send Slack message: %s", response['error'])
            return False
            
    except Exception as e:
        logger.error("❌ Error sending Slack message: %s", str(e))
        return False

# ✅ Load emails from JSON
def load_emails_from_json(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            emails = json.load(f)
        print(f"✅ Loaded {len(emails)} emails from JSON.")
        return emails
    except Exception as e:
        print(f"❌ Error loading JSON: {e}")
        return []

# ✅ Chunk long text
def chunk_text(text, max_chunk_size=1024):
    words = text.split()
    chunks = []
    current_chunk = []

    for word in words:
        current_chunk.append(word)
        if len(" ".join(current_chunk)) > max_chunk_size:
            chunks.append(" ".join(current_chunk[:-1]))
            current_chunk = [word]
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks

# ✅ Summarize email body
def summarize_email(email_body, max_length=150):
    if not AI_ENABLED:
        return email_body[:200] + "..." if len(email_body) > 200 else email_body
        
    if len(email_body) < 100:  # Don't summarize very short emails
        return email_body
    
    try:
        # Process only the first 500 characters to avoid memory issues
        truncated_body = email_body[:500]
        # T5 requires "summarize: " prefix
        input_text = "summarize: " + truncated_body
        summary = summarizer(input_text, max_length=max_length, min_length=30, do_sample=False)[0]['summary_text']
        return summary
    except Exception as e:
        print(f"⚠️ Failed to summarize: {e}")
        # Return a truncated version of the original text if summarization fails
        return email_body[:200] + "..."

# ✅ Classify email intent
def classify_intent(email_body):
    """Classify the intent of the email."""
    if not AI_ENABLED:
        return "General Inquiry"  # Default intent when AI is disabled
        
    # Enhanced labels to better identify events
    labels = [
        "Event", 
        "Meeting", 
        "Appointment", 
        "Request", 
        "Follow-up", 
        "Complaint", 
        "Approval", 
        "General Inquiry"
    ]
    
    # Check for date patterns in the email body
    date_patterns = [
        r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
        r'(\d{2}/\d{2}/\d{4})',  # DD/MM/YYYY
        r'(\d{2}-\d{2}-\d{4})',  # DD-MM-YYYY
        r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)',  # Time patterns
        r'(?:at|on)\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December))'  # Natural date patterns
    ]
    
    # Check for meeting/event keywords
    meeting_keywords = [
        'meeting', 'appointment', 'schedule', 'calendar', 'event',
        'interview', 'call', 'conference', 'discussion', 'catch up',
        'get together', 'gathering', 'celebration', 'party', 'lunch',
        'dinner', 'breakfast', 'coffee', 'video call',
        'zoom', 'teams', 'google meet', 'webex', 'skype'
    ]
    
    # Check for time-related keywords
    time_keywords = [
        'at', 'on', 'from', 'to', 'between', 'during',
        'morning', 'afternoon', 'evening', 'night',
        'today', 'tomorrow', 'this week', 'next week',
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
        'saturday', 'sunday'
    ]
    
    # Convert email body to lowercase for case-insensitive matching
    email_lower = email_body.lower()
    
    # Check for date patterns
    has_date = any(re.search(pattern, email_body) for pattern in date_patterns)
    
    # Check for meeting keywords
    has_meeting_keywords = any(keyword in email_lower for keyword in meeting_keywords)
    
    # Check for time keywords
    has_time_keywords = any(keyword in email_lower for keyword in time_keywords)
    
    # If we find date patterns and meeting/time keywords, it's likely a meeting/event
    if has_date and (has_meeting_keywords or has_time_keywords):
        return "Meeting"  # Override with Meeting if patterns are found
        
    result = classifier(email_body, candidate_labels=labels, multi_label=True)
    return result['labels'][0]

# ✅ Extract request type
def extract_request_type(email_body):
    """Extract the type of request from the email."""
    if not AI_ENABLED:
        return "Information Request"  # Default request type when AI is disabled
        
    # Enhanced request labels to better identify events
    request_labels = [
        "Calendar Event", 
        "Meeting Request", 
        "Appointment Request", 
        "Approval Request", 
        "Support Request", 
        "Information Request"
    ]
    
    # Check for event-related keywords
    event_keywords = [
        'happening on', 'scheduled for', 'at', 'time', 'date',
        'event', 'celebration', 'get-together', 'party', 'gathering',
        'meeting', 'appointment', 'interview', 'call', 'conference',
        'discussion', 'catch up', 'lunch', 'dinner', 'breakfast',
        'coffee', 'video call', 'zoom', 'teams', 'google meet',
        'webex', 'skype'
    ]
    
    # Check for date patterns
    date_patterns = [
        r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
        r'(\d{2}/\d{2}/\d{4})',  # DD/MM/YYYY
        r'(\d{2}-\d{2}-\d{4})',  # DD-MM-YYYY
        r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)',  # Time patterns
        r'(?:at|on)\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December))'  # Natural date patterns
    ]
    
    # Convert email body to lowercase for case-insensitive matching
    email_lower = email_body.lower()
    
    # Check for event keywords
    has_event_keywords = any(keyword in email_lower for keyword in event_keywords)
    
    # Check for date patterns
    has_date = any(re.search(pattern, email_body) for pattern in date_patterns)
    
    # If we find event keywords and date patterns, it's likely a calendar event
    if has_event_keywords and has_date:
        return "Calendar Event"  # Override with Calendar Event if patterns are found
        
    result = classifier(email_body, candidate_labels=request_labels, multi_label=True)
    return result['labels'][0]

# ✅ Generate GPT-2 reply
def generate_ai_reply(email_subject, email_body, sender="there"):
    print("🧠 Generating reply...")

    try:
        # Get sender name
        sender_name = sender.split('<')[0].strip() if '<' in sender else sender
        
        if not AI_ENABLED:
            return (
                f"Hi {sender_name},\n\n"
                f"Thank you for your message regarding \"{email_subject}\".\n\n"
                f"I will review your message and get back to you soon.\n\n"
                f"Best regards,\n"
                f"Vishal"
            )
            
        # Get a clean summary
        summary = summarize_email(email_body, max_length=100)
        
        # Extract intent and request type
        intent = classify_intent(email_body[:500])  # Use truncated text for classification
        request_type = extract_request_type(email_body[:500])
        
        # Template-based response based on intent and request type
        response_body = ""
        if "meeting" in email_subject.lower() or request_type == "Meeting Request":
            response_body = (
                f"Thank you for the invitation. I have noted the details and will check my calendar. "
                f"I will confirm my availability shortly."
            )
        elif intent == "Request":
            response_body = (
                f"I acknowledge your request and will review it carefully. "
                f"I'll get back to you with a response soon."
            )
        elif intent == "Follow-up":
            response_body = (
                f"Thank you for following up. I'm currently reviewing this matter and "
                f"will provide an update shortly."
            )
        elif intent == "Complaint":
            response_body = (
                f"I understand your concern regarding this matter. I will look into this "
                f"and get back to you with a resolution as soon as possible."
            )
        else:
            response_body = (
                f"I've reviewed your message and will respond appropriately. "
                f"Thank you for reaching out."
            )

        reply = (
            f"Hi {sender_name},\n\n"
            f"Thank you for your message regarding \"{email_subject}\".\n\n"
            f"{response_body}\n\n"
            f"Best regards,\n"
            f"Vishal"
        )
        
        return reply

    except Exception as e:
        print(f"⚠️ Failed to generate reply: {e}")
        return f"Hi {sender_name},\n\nThank you for your message. I will review and respond shortly.\n\nBest regards,\nVishal"

# ✅ Web search via Google API
def search_web(query):
    if not AI_ENABLED:
        return []
        
    if os.getenv('DEVELOPMENT_MODE', '').lower() == 'true':
        # Return mock search results in development mode
        logger.info("Development mode: Returning mock search results")
        return [
            {
                "title": "Mock Search Result 1",
                "link": "https://example.com/result1",
                "snippet": "This is a mock search result for development testing."
            },
            {
                "title": "Mock Search Result 2",
                "link": "https://example.com/result2",
                "snippet": "Another mock result to simulate web search functionality."
            }
        ]

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'q': query,
        'key': GOOGLE_API_KEY,
        'cx': SEARCH_ENGINE_ID,
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        search_results = response.json().get('items', [])
        return [{"title": item['title'], "link": item['link'], "snippet": item['snippet']} for item in search_results]
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Web search failed: {e}")
        return []

def create_calendar_event(email_data):
    """Create a calendar event from email data."""
    try:
        if os.getenv('DEVELOPMENT_MODE', '').lower() == 'true':
            logger.info("Development mode: Would create calendar event:")
            logger.info(f"Subject: {email_data['subject']}")
            logger.info(f"Time: {email_data['meeting_time']}")
            logger.info(f"Description: {email_data['body'][:100]}...")  # First 100 chars
            return True
            
        # Get service account credentials file path
        service_account_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'configuration',
            'service_account.json'
        )
        
        if not os.path.exists(service_account_file):
            logger.error("❌ Service account file not found")
            return False
            
        # Create credentials
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=['https://www.googleapis.com/auth/calendar']
        )
        
        # Build the calendar service
        service = build('calendar', 'v3', credentials=credentials)
        
        # Create event
        event = {
            'summary': email_data['subject'],
            'description': email_data['body'],
            'start': {
                'dateTime': email_data['meeting_time'].isoformat(),
                'timeZone': 'Asia/Kolkata',  # IST timezone
            },
            'end': {
                'dateTime': (email_data['meeting_time'] + timedelta(hours=1)).isoformat(),
                'timeZone': 'Asia/Kolkata',
            },
            'reminders': {
                'useDefault': True,
            }
        }
        
        # Insert event
        event = service.events().insert(
            calendarId='primary',
            body=event
        ).execute()
        
        logger.info(f"✅ Calendar event created: {event.get('htmlLink')}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating calendar event: {str(e)}")
        return False

# ✅ Email processing pipeline
def process_emails(file_path):
    """Process emails from JSON file."""
    print(f"\n🔍 Processing emails from {file_path}...")
    
    # Initialize timing and cycle count
    start_time = time.time()
    cycle_count = 1
    
    # Load emails
    emails = load_emails_from_json(file_path)
    if not emails:
        return
    
    processed_emails = []
    
    # Wait for TensorFlow to finish initialization
    print("\nInitialization complete. Starting email processing...\n")
    
    for email in emails:
        try:
            # Extract email details
            sender = email.get('from', 'Unknown Sender')
            subject = email.get('subject', 'No Subject')
            body = email.get('body', '')
            
            print(f"\n📩 From: {sender} | Subject: {subject}")
            print("🧠 Generating reply...")
            
            # Generate summary
            summary = summarize_email(body)
            print(f"📝 Summary: {summary}")
            
            # Classify intent and request type
            intent = classify_intent(body)
            request_type = extract_request_type(body)
            print(f"📌 Intent: {intent} | Request Type: {request_type}")
            
            # Generate AI reply
            reply = generate_ai_reply(subject, body, sender)
            print(f"🤖 AI Reply:\n{reply}")
            
            # Check for meeting intent
            if intent in ["Event", "Meeting", "Appointment"] or request_type in ["Calendar Event", "Meeting Request", "Appointment Request"]:
                print("📅 Detected potential meeting intent...")
                print("🔍 Analyzing email body:")
                print(body)
                print("🔍 Searching for date...")
                
                # Extract meeting details
                meeting_time = extract_meeting_details(body)
                if meeting_time:
                    print(f"  Found date: {meeting_time.strftime('%Y-%m-%d')}")
                    print(f"  Parsed date: {meeting_time.strftime('%Y-%m-%d')}")
                    print("🔍 Searching for time...")
                    print(f"  Found time: {meeting_time.strftime('%I:%M %p')}")
                    print(f"  Parsed time: {meeting_time.strftime('%H:%M')}")
                    print(f"📆 Found meeting details - Date: {meeting_time.strftime('%Y-%m-%d')}, Time: {meeting_time.strftime('%H:%M')}")
                    
                    # Create calendar event
                    event_data = {
                        'subject': subject,
                        'body': body,
                        'meeting_time': meeting_time
                    }
                    event_link = create_calendar_event(event_data)
                    if event_link:
                        print(f"✅ Google Calendar event created: {event_link}")
            
            # Add to processed emails
            processed_emails.append({
                'from': sender,
                'subject': subject,
                'summary': summary,
                'intent': intent,
                'request_type': request_type,
                'ai_reply': reply,
                'calendar_event_created': bool(meeting_time),
                'processed_at': datetime.now().isoformat()
            })
            
        except Exception as e:
            print(f"⚠️ Error processing email: {str(e)}")
            continue
    
    # Save processed emails
    if processed_emails:
        output_dir = os.path.join(os.path.dirname(file_path), 'processed')
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, 'processed_emails.json')
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(processed_emails, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Saved processed emails to '{output_file}'")
        except Exception as e:
            print(f"⚠️ Error saving processed emails: {str(e)}")
    
    print(f"\n✅ Finished processing {len(processed_emails)} emails.")
    logger.info(f"✅ Successfully processed {len(processed_emails)} emails")
    logger.info(f"✅ Email pipeline completed successfully in {time.time() - start_time:.2f} seconds!")
    logger.info(f"💤 Cycle {cycle_count} completed. Waiting 5 minutes before next run...")

def extract_meeting_details(email_body):
    """Extract meeting date and time from email body."""
    try:
        print("📅 Detected potential meeting intent...")
        print("🔍 Analyzing email body:")
        print(email_body)
        print("🔍 Searching for date...")
        
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
                print(f"  Found date: {date}")
                print(f"  Parsed date: {date}")
                break
                
        print("🔍 Searching for time...")
        for pattern in time_patterns:
            match = re.search(pattern, email_body)
            if match:
                time = match.group(1)
                print(f"  Found time: {time}")
                break
                
        if date and time:
            # Convert time to 24-hour format if needed
            if 'AM' in time or 'PM' in time:
                time_obj = datetime.strptime(time, '%I:%M %p')
                time = time_obj.strftime('%H:%M')
                print(f"  Parsed time: {time}")
                
            # Create datetime object
            meeting_time = datetime.strptime(f"{date} {time}", '%Y-%m-%d %H:%M')
            print(f"📆 Found meeting details - Date: {date}, Time: {time}")
            return meeting_time
            
        return None
        
    except Exception as e:
        logger.error(f"⚠️ Error extracting meeting details: {str(e)}")
        return None

def process_emails_with_ai(emails):
    """Process emails using AI features."""
    processed_count = 0
    processed_emails = []  # List to store processed emails
    
    for email in emails:
        try:
            print(f"\n📧 Processing email: {email['subject']}")
            
            # Generate summary
            summary = summarize_email(email['body'])
            
            # Classify intent and request type
            intent = classify_intent(email['body'])
            request_type = extract_request_type(email['body'])
            
            print(f"🔍 Intent: {intent}")
            print(f"🔍 Request Type: {request_type}")
            
            # Generate AI reply
            reply = generate_ai_reply(email['subject'], email['body'], email['from'])
            
            # Send Slack notification
            slack_message = f":envelope_with_arrow: *New Important Email*\n\n*Subject*: {email['subject']}\n*Body*: {summary}"
            send_slack_message(slack_message)
            
            # Check for event/meeting intent and create calendar event
            calendar_event_created = False
            if (intent in ["Event", "Meeting", "Appointment"] or 
                request_type in ["Calendar Event", "Meeting Request", "Appointment Request"]):
                print("\n📅 Detected potential meeting intent...")
                print("🔍 Analyzing email body:")
                print(email['body'])
                print("🔍 Searching for date and time...")
                
                # Extract date patterns
                date_patterns = [
                    r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
                    r'(\d{2}/\d{2}/\d{4})',  # DD/MM/YYYY
                    r'(\d{2}-\d{2}-\d{4})'   # DD-MM-YYYY
                ]
                
                # Extract time patterns
                time_patterns = [
                    r'(\d{1,2}:\d{2}\s*[AP]M)',  # 12-hour format
                    r'(\d{2}:\d{2})'              # 24-hour format
                ]
                
                # Search for date
                date = None
                for pattern in date_patterns:
                    match = re.search(pattern, email['body'])
                    if match:
                        date = match.group(1)
                        print(f"  Found date: {date}")
                        break
                
                # Search for time
                time = None
                for pattern in time_patterns:
                    match = re.search(pattern, email['body'])
                    if match:
                        time = match.group(1)
                        print(f"  Found time: {time}")
                        break
                
                if date and time:
                    print(f"📆 Found meeting details - Date: {date}, Time: {time}")
                    try:
                        # Convert time to 24-hour format if needed
                        if 'AM' in time or 'PM' in time:
                            time_obj = datetime.strptime(time, '%I:%M %p')
                            time = time_obj.strftime('%H:%M')
                            
                        # Create datetime object
                        meeting_time = datetime.strptime(f"{date} {time}", '%Y-%m-%d %H:%M')
                        
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
                    except Exception as e:
                        print(f"⚠️ Error creating calendar event: {str(e)}")
                else:
                    print("❌ No date and time found in the email")
            
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
            
        except Exception as e:
            print(f"⚠️ Error processing email: {str(e)}")
            continue
    
    print(f"\n✅ Finished processing {processed_count} emails.")
    logger.info(f"✅ Successfully processed {processed_count} emails")
    
    return processed_emails