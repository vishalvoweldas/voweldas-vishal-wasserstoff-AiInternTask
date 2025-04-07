import json
import os
import shutil
from datetime import datetime
from gmail_fetcher import GmailFetcher, save_emails
from email.utils import parsedate_to_datetime

def format_email_preview(body: str, max_length: int = 100) -> str:
    """Format email body preview with smart truncation."""
    if not body:
        return "No content"
    
    preview = body.replace('\n', ' ').strip()
    if len(preview) > max_length:
        # Try to truncate at word boundary
        truncated = preview[:max_length].rsplit(' ', 1)[0]
        return f"{truncated}..."
    return preview

def format_date(date_str: str) -> str:
    """Format email date in a readable format."""
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.strftime("%Y-%m-%d %I:%M %p")
    except Exception:
        return date_str

def clear_email_directory(base_dir: str = "emails"):
    """Clear all existing email data."""
    try:
        if os.path.exists(base_dir):
            print(f"🗑️ Clearing existing email data from {base_dir}")
            shutil.rmtree(base_dir)
            print("✅ Existing data cleared successfully")
    except Exception as e:
        print(f"⚠️ Error clearing email directory: {e}")

def save_emails_by_date(emails: list, base_dir: str = "emails", clear_existing: bool = True) -> str:
    """Save emails organized by date."""
    if not emails:
        return ""
        
    try:
        # Clear existing data if requested
        if clear_existing:
            clear_email_directory(base_dir)
        
        # Create base directory
        os.makedirs(base_dir, exist_ok=True)
        
        # Get today's date for the filename
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Create directory for today
        date_dir = os.path.join(base_dir, today)
        os.makedirs(date_dir, exist_ok=True)
        
        # Save emails with timestamp
        timestamp = datetime.now().strftime("%H-%M-%S")
        filename = os.path.join(date_dir, f"emails_{timestamp}.json")
        
        # Also save to the root emails.json for compatibility
        try:
            with open("emails.json", "w", encoding="utf-8") as f:
                json.dump(emails, f, indent=2, ensure_ascii=False)
            print("✅ Saved emails to emails.json")
        except Exception as e:
            print(f"⚠️ Error saving to emails.json: {e}")
        
        # Save to date-organized directory
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(emails, f, indent=2, ensure_ascii=False)
            
        return filename
        
    except Exception as e:
        print(f"❌ Error saving emails: {e}")
        return ""

def fetch_once(limit: int = 4, save_dir: str = "emails", clear_existing: bool = True):
    """Fetch emails once without continuous loop."""
    print("\n🔄 Starting email fetch...")
    
    fetcher = GmailFetcher()
    emails = fetcher.fetch_emails(limit=limit)
    
    if emails:
        # Save emails organized by date
        saved_file = save_emails_by_date(emails, save_dir, clear_existing)
        if saved_file:
            print(f"✅ Successfully saved {len(emails)} emails to {saved_file}")
        
        # Print detailed email information
        print("\n📥 Fetched Emails:")
        print("=" * 80)
        
        for i, email in enumerate(emails, 1):
            print(f"\n📧 Email {i}/{len(emails)}:")
            print("─" * 40)
            print(f"From: {email['from']}")
            print(f"Subject: {email['subject']}")
            print(f"Date: {format_date(email['date'])}")
            
            # Display email preview
            preview = format_email_preview(email['body'])
            print(f"Preview: {preview}")
            
            # Display email size
            email_size = len(json.dumps(email, ensure_ascii=False).encode('utf-8'))
            print(f"Size: {email_size / 1024:.1f} KB")
            
            # Check for attachments or HTML content
            if email.get('body'):
                has_html = '<html' in email['body'].lower()
                has_attachment = '[attachment]' in email['body'].lower() or 'Content-Disposition: attachment' in email['body']
                
                if has_html or has_attachment:
                    print("Contains:", end=" ")
                    if has_html:
                        print("🌐 HTML", end=" ")
                    if has_attachment:
                        print("📎 Attachments", end=" ")
                    print()
            
            print("─" * 40)
    else:
        print("❌ No emails were fetched.")

def display_email_stats(save_dir: str = "emails"):
    """Display statistics about saved emails."""
    try:
        if not os.path.exists(save_dir):
            print("\n📊 Email Statistics: No emails found")
            return
            
        total_emails = 0
        total_size = 0
        dates = []
        
        for root, dirs, files in os.walk(save_dir):
            for file in files:
                if file.endswith('.json'):
                    file_path = os.path.join(root, file)
                    size = os.path.getsize(file_path)
                    total_size += size
                    
                    with open(file_path, 'r', encoding='utf-8') as f:
                        emails = json.load(f)
                        total_emails += len(emails)
                        
                    dates.append(os.path.basename(os.path.dirname(file_path)))
        
        if dates:
            print("\n📊 Email Statistics:")
            print(f"Total Emails: {total_emails}")
            print(f"Total Size: {total_size / (1024*1024):.2f} MB")
            print(f"Date Range: {min(dates)} to {max(dates)}")
            print(f"Days with Emails: {len(set(dates))}")
        else:
            print("\n📊 Email Statistics: No emails found")
            
    except Exception as e:
        print(f"❌ Error displaying statistics: {e}")

if __name__ == "__main__":
    SAVE_DIR = "emails"  # Directory to save emails
    fetch_once(limit=4, save_dir=SAVE_DIR, clear_existing=True)  # Set clear_existing=False to keep old emails
    display_email_stats(SAVE_DIR) 