import sqlite3
import psycopg2
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Union
from dataclasses import dataclass
from contextlib import contextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

@dataclass
class ThreadInfo:
    thread_id: str
    subject: str
    participants: List[str]
    last_updated: datetime
    message_count: int

class BaseDatabase:
    """Base class for database operations"""
    
    def __init__(self):
        self.setup_tables()
    
    def setup_tables(self):
        """Create necessary tables if they don't exist"""
        raise NotImplementedError
        
    def save_email(self, email_data: Dict) -> str:
        """Save email and return its ID"""
        raise NotImplementedError
        
    def save_processed_email(self, email_id: str, processed_data: Dict):
        """Save processed email data"""
        raise NotImplementedError
        
    def save_calendar_event(self, email_id: str, event_data: Dict):
        """Save calendar event details"""
        raise NotImplementedError
        
    def link_email_thread(self, reply_id: str, original_id: str):
        """Link reply to original email in thread"""
        raise NotImplementedError
        
    def get_thread_history(self, thread_id: str) -> List[Dict]:
        """Retrieve full conversation history"""
        raise NotImplementedError

    def get_thread_participants(self, thread_id: str) -> List[str]:
        """Get all participants in a thread"""
        raise NotImplementedError
        
    def get_thread_summary(self, thread_id: str) -> Dict:
        """Get summary information about a thread"""
        raise NotImplementedError
        
    def search_threads(self, query: str) -> List[Dict]:
        """Search through email threads"""
        raise NotImplementedError
        
    def get_recent_threads(self, limit: int = 10) -> List[Dict]:
        """Get most recent threads"""
        raise NotImplementedError

class SQLiteDatabase(BaseDatabase):
    def __init__(self, db_path: str = "emails.db"):
        self.db_path = db_path
        super().__init__()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def setup_tables(self):
        """Create all necessary tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Emails table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS emails (
                    id TEXT PRIMARY KEY,
                    sender TEXT,
                    subject TEXT,
                    body TEXT,
                    received_date TIMESTAMP,
                    thread_id TEXT,
                    in_reply_to TEXT,
                    references TEXT,
                    raw_data JSON
                )
            """)
            
            # Thread table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    thread_id TEXT PRIMARY KEY,
                    subject TEXT,
                    participants JSON,
                    last_updated TIMESTAMP,
                    message_count INTEGER
                )
            """)
            
            # Processed emails table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_emails (
                    email_id TEXT PRIMARY KEY,
                    summary TEXT,
                    intent TEXT,
                    request_type TEXT,
                    ai_reply TEXT,
                    processed_date TIMESTAMP,
                    FOREIGN KEY (email_id) REFERENCES emails (id)
                )
            """)
            
            # Calendar events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS calendar_events (
                    id TEXT PRIMARY KEY,
                    email_id TEXT,
                    event_title TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    attendees JSON,
                    calendar_link TEXT,
                    FOREIGN KEY (email_id) REFERENCES emails (id)
                )
            """)
            
            conn.commit()

    def save_email(self, email_data: Dict) -> str:
        """Save email and return its ID"""
        email_id = email_data.get('id', str(datetime.now().timestamp()))
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO emails (
                    id, sender, subject, body, received_date, 
                    thread_id, in_reply_to, references, raw_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                email_id,
                email_data.get('from'),
                email_data.get('subject'),
                email_data.get('body'),
                email_data.get('date'),
                email_data.get('thread_id'),
                email_data.get('in_reply_to'),
                json.dumps(email_data.get('references', [])),
                json.dumps(email_data)
            ))
            conn.commit()
            
            # Update thread information
            self._update_thread_info(cursor, email_data)
            conn.commit()
            
        return email_id
    
    def _update_thread_info(self, cursor, email_data: Dict):
        """Update thread information"""
        thread_id = email_data.get('thread_id')
        if not thread_id:
            return
            
        # Get existing thread or create new
        cursor.execute("SELECT * FROM threads WHERE thread_id = ?", (thread_id,))
        thread = cursor.fetchone()
        
        if thread:
            # Update existing thread
            cursor.execute("""
                UPDATE threads 
                SET message_count = message_count + 1,
                    last_updated = ?,
                    participants = ?
                WHERE thread_id = ?
            """, (
                datetime.now(),
                json.dumps(self._update_participants(
                    json.loads(thread['participants']),
                    email_data.get('from')
                )),
                thread_id
            ))
        else:
            # Create new thread
            cursor.execute("""
                INSERT INTO threads (
                    thread_id, subject, participants, last_updated, message_count
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                thread_id,
                email_data.get('subject'),
                json.dumps([email_data.get('from')]),
                datetime.now(),
                1
            ))
    
    def _update_participants(self, existing: List[str], new_participant: str) -> List[str]:
        """Update participant list"""
        if new_participant not in existing:
            existing.append(new_participant)
        return existing
    
    def save_processed_email(self, email_id: str, processed_data: Dict):
        """Save processed email data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO processed_emails (
                    email_id, summary, intent, request_type, ai_reply, processed_date
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                email_id,
                processed_data.get('summary'),
                processed_data.get('intent'),
                processed_data.get('request_type'),
                processed_data.get('ai_reply'),
                datetime.now()
            ))
            conn.commit()
    
    def save_calendar_event(self, email_id: str, event_data: Dict):
        """Save calendar event details"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO calendar_events (
                    id, email_id, event_title, start_time, end_time, 
                    attendees, calendar_link
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                str(datetime.now().timestamp()),
                email_id,
                event_data.get('title'),
                event_data.get('start_time'),
                event_data.get('end_time'),
                json.dumps(event_data.get('attendees', [])),
                event_data.get('calendar_link')
            ))
            conn.commit()
    
    def link_email_thread(self, reply_id: str, original_id: str):
        """Link reply to original email in thread"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get original email's thread_id
            cursor.execute("SELECT thread_id FROM emails WHERE id = ?", (original_id,))
            original = cursor.fetchone()
            
            if original and original['thread_id']:
                # Update reply with thread_id and reference
                cursor.execute("""
                    UPDATE emails 
                    SET thread_id = ?,
                        in_reply_to = ?,
                        references = ?
                    WHERE id = ?
                """, (
                    original['thread_id'],
                    original_id,
                    json.dumps([original_id]),
                    reply_id
                ))
                conn.commit()
    
    def get_thread_history(self, thread_id: str) -> List[Dict]:
        """Retrieve full conversation history with context"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get all emails in thread with their processed data
            cursor.execute("""
                SELECT e.*, 
                       p.summary, p.intent, p.ai_reply,
                       c.event_title, c.start_time, c.end_time,
                       c.calendar_link
                FROM emails e
                LEFT JOIN processed_emails p ON e.id = p.email_id
                LEFT JOIN calendar_events c ON e.id = c.email_id
                WHERE e.thread_id = ?
                ORDER BY e.received_date ASC
            """, (thread_id,))
            
            emails = []
            for row in cursor.fetchall():
                email_data = dict(row)
                
                # Parse JSON fields
                email_data['raw_data'] = json.loads(email_data['raw_data'])
                email_data['references'] = json.loads(email_data['references'])
                
                # Add meeting info if exists
                if email_data['event_title']:
                    email_data['meeting_details'] = {
                        'title': email_data['event_title'],
                        'start_time': email_data['start_time'],
                        'end_time': email_data['end_time'],
                        'calendar_link': email_data['calendar_link']
                    }
                
                # Clean up response
                for field in ['event_title', 'start_time', 'end_time', 'calendar_link']:
                    email_data.pop(field, None)
                
                emails.append(email_data)
            
            # Get thread summary
            thread_summary = self.get_thread_summary(thread_id)
            
            return {
                'thread_info': thread_summary,
                'emails': emails
            }

    def get_thread_participants(self, thread_id: str) -> List[str]:
        """Get all participants in a thread"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT sender
                FROM emails
                WHERE thread_id = ?
                ORDER BY received_date ASC
            """, (thread_id,))
            return [row['sender'] for row in cursor.fetchall()]

    def get_thread_summary(self, thread_id: str) -> Dict:
        """Get summary information about a thread"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get thread info
            cursor.execute("""
                SELECT t.*, 
                       COUNT(DISTINCT e.id) as email_count,
                       MIN(e.received_date) as start_date,
                       MAX(e.received_date) as last_activity,
                       GROUP_CONCAT(DISTINCT e.sender) as participants
                FROM threads t
                JOIN emails e ON t.thread_id = e.thread_id
                WHERE t.thread_id = ?
                GROUP BY t.thread_id
            """, (thread_id,))
            
            thread = cursor.fetchone()
            if not thread:
                return None
                
            # Get the latest email in thread
            cursor.execute("""
                SELECT e.*, p.summary, p.intent
                FROM emails e
                LEFT JOIN processed_emails p ON e.id = p.email_id
                WHERE e.thread_id = ?
                ORDER BY e.received_date DESC
                LIMIT 1
            """, (thread_id,))
            
            latest = cursor.fetchone()
            
            return {
                "thread_id": thread['thread_id'],
                "subject": thread['subject'],
                "participants": thread['participants'].split(','),
                "email_count": thread['email_count'],
                "start_date": thread['start_date'],
                "last_activity": thread['last_activity'],
                "latest_email": {
                    "subject": latest['subject'],
                    "sender": latest['sender'],
                    "summary": latest['summary'],
                    "intent": latest['intent']
                } if latest else None
            }

    def search_threads(self, query: str) -> List[Dict]:
        """Search through email threads"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            search_term = f"%{query}%"
            cursor.execute("""
                SELECT DISTINCT t.thread_id, t.subject,
                       COUNT(DISTINCT e.id) as email_count,
                       MAX(e.received_date) as last_activity
                FROM threads t
                JOIN emails e ON t.thread_id = e.thread_id
                LEFT JOIN processed_emails p ON e.id = p.email_id
                WHERE e.subject LIKE ?
                   OR e.body LIKE ?
                   OR p.summary LIKE ?
                GROUP BY t.thread_id
                ORDER BY last_activity DESC
            """, (search_term, search_term, search_term))
            
            threads = []
            for row in cursor.fetchall():
                thread_summary = self.get_thread_summary(row['thread_id'])
                if thread_summary:
                    threads.append(thread_summary)
            
            return threads

    def get_recent_threads(self, limit: int = 10) -> List[Dict]:
        """Get most recent threads"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT t.thread_id
                FROM threads t
                JOIN emails e ON t.thread_id = e.thread_id
                GROUP BY t.thread_id
                ORDER BY MAX(e.received_date) DESC
                LIMIT ?
            """, (limit,))
            
            threads = []
            for row in cursor.fetchall():
                thread_summary = self.get_thread_summary(row['thread_id'])
                if thread_summary:
                    threads.append(thread_summary)
            
            return threads

class PostgreSQLDatabase(BaseDatabase):
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        super().__init__()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = psycopg2.connect(self.connection_string)
        try:
            yield conn
        finally:
            conn.close()
    
    def setup_tables(self):
        """Create all necessary tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Emails table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS emails (
                    id TEXT PRIMARY KEY,
                    sender TEXT,
                    subject TEXT,
                    body TEXT,
                    received_date TIMESTAMP,
                    thread_id TEXT,
                    in_reply_to TEXT,
                    references JSONB,
                    raw_data JSONB
                )
            """)
            
            # Thread table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    thread_id TEXT PRIMARY KEY,
                    subject TEXT,
                    participants JSONB,
                    last_updated TIMESTAMP,
                    message_count INTEGER
                )
            """)
            
            # Processed emails table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_emails (
                    email_id TEXT PRIMARY KEY,
                    summary TEXT,
                    intent TEXT,
                    request_type TEXT,
                    ai_reply TEXT,
                    processed_date TIMESTAMP,
                    FOREIGN KEY (email_id) REFERENCES emails (id)
                )
            """)
            
            # Calendar events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS calendar_events (
                    id TEXT PRIMARY KEY,
                    email_id TEXT,
                    event_title TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    attendees JSONB,
                    calendar_link TEXT,
                    FOREIGN KEY (email_id) REFERENCES emails (id)
                )
            """)
            
            conn.commit()
    
    # Note: The rest of the PostgreSQL implementation follows the same pattern
    # as SQLite but uses PostgreSQL-specific features like JSONB
    # Implementation continues with similar methods as SQLite...

# Factory function to create appropriate database instance
def create_database(db_type: str = "sqlite", **kwargs) -> BaseDatabase:
    """Create database instance based on type"""
    if db_type.lower() == "sqlite":
        return SQLiteDatabase(**kwargs)
    elif db_type.lower() == "postgresql":
        return PostgreSQLDatabase(**kwargs)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")

# Example usage
if __name__ == "__main__":
    db = create_database()
    # Test database operations here 