# Technical Documentation

## System Architecture & Design Decisions

## Key Technical Decisions

### 1. Authentication & Security
- **Decision**: Implemented OAuth2 with service accounts
- **Rationale**:
  - More secure than password-based auth
  - Supports token refresh without user intervention
  - Enables fine-grained access control
  - Industry standard for Google APIs
- **Impact**:
  - Improved security posture
  - Reduced maintenance overhead
  - Better user experience (no password management)
  - Seamless integration with Google services

### 2. Data Storage & Format
- **Decision**: JSON-based file storage with structured directories
- **Rationale**:
  - Human-readable format for easy debugging
  - No database setup required for simple deployments
  - Version control friendly
  - Easy to backup and restore
- **Impact**:
  - Simplified development workflow
  - Easier troubleshooting
  - Quick setup for new deployments
  - Straightforward data migration

### 3. AI Model Selection
- **Decision**: Used lightweight, pre-trained models (T5-small, DistilRoBERTa, GPT-2)
- **Rationale**:
  - Balance between performance and resource usage
  - No need for custom training
  - Good community support
  - Proven reliability
- **Impact**:
  - Faster processing times
  - Lower hardware requirements
  - Reduced operational costs
  - Easier maintenance

### 4. Pipeline Architecture
- **Decision**: Modular pipeline with clear separation of concerns
- **Rationale**:
  - Each component handles specific functionality
  - Easy to test and debug
  - Simple to extend or modify
  - Clear data flow
- **Impact**:
  - Better code organization
  - Easier maintenance
  - Simplified testing
  - Flexible for future enhancements

### 1. Email Fetching & Storage

#### Gmail Integration
- **Authentication Method**: OAuth2 with service account
- **Design Decision**: Chose OAuth2 over basic authentication for:
  - Enhanced security
  - No need to store raw passwords
  - Granular permission control
  - Token refresh capability

#### Email Storage Strategy
```python
# Storage Structure
data/
├── raw/           # Original emails
│   └── emails.json
└── processed/     # Processed results
    └── processed_emails.json
```

- **Format**: JSON for:
  - Human readability
  - Easy version control
  - Simple backup/restore
- **Backup System**: Daily backups in `emails/YYYY-MM-DD/`
- **Rate Limiting**: 4 emails per fetch to avoid API limits

### 2. Email Processing Pipeline

#### Cleaning & Normalization
```python
class EmailCleaner:
    def __init__(self):
        self.patterns = {
            'headers': [r'From:.*\n', ...],
            'forwarded': [r'--\s*Forwarded message.*', ...],
            'replies': [r'On.*wrote:.*', ...],
            'signatures': [r'--\s*\n.*', ...],
            'whitespace': [r'\s+', ...],
            'quoted': [r'>.*\n', ...],
            'attachments': [r'\[image:.*\]', ...]
        }
```

- **Design Decision**: Regex-based cleaning for:
  - Performance optimization
  - Consistent formatting
  - Removal of noise
- **Challenge Solved**: Unicode handling using `chardet` for encoding detection

#### Meeting Detection
```python
# Date/Time Pattern Examples
date_patterns = [
    r'(\d{4}-\d{2}-\d{2})',          # YYYY-MM-DD
    r'(\d{2}/\d{2}/\d{4})',          # DD/MM/YYYY
    r'(\d{2}-\d{2}-\d{4})',          # DD-MM-YYYY
    r'(\d{4}-[A-Za-z]{3}-\d{2})',    # YYYY-MMM-DD
]

time_patterns = [
    r'(\d{1,2}:\d{2}\s*[AP]M)',      # 12-hour format
    r'(\d{2}:\d{2})',                # 24-hour format
]
```

- **Challenge Solved**: Multiple date/time formats using flexible regex patterns
- **Validation**: Datetime parsing to ensure valid dates

### 3. AI Model Integration

#### Model Selection
1. **Text Summarization**: T5-small
   - Balanced between performance and resource usage
   - Good at maintaining context
   ```python
   summarizer = pipeline("summarization", model="t5-small", device=-1)
   ```

2. **Intent Classification**: DistilRoBERTa
   - Lightweight but accurate
   - Zero-shot capability
   ```python
   classifier = pipeline("zero-shot-classification", 
                       model="cross-encoder/nli-distilroberta-base")
   ```

3. **Reply Generation**: GPT-2
   - Good balance of coherence and speed
   - Manageable resource requirements
   ```python
   gpt2_tokenizer = AutoTokenizer.from_pretrained("gpt2")
   gpt2_model = AutoModelForCausalLM.from_pretrained("gpt2")
   ```

#### Prompt Engineering
```python
# Example prompt templates
meeting_prompt = f"Extract meeting details from: {email_body}"
reply_prompt = f"Write a {tone} reply to: {subject}\n\nDear {sender},\n"
```

- **Design Decision**: Template-based prompts for:
  - Consistency in responses
  - Easy modification
  - Better control over output

### 4. External Integrations

#### Google Calendar
- **Event Creation**: Automatic for detected meetings
- **Challenge Solved**: Timezone handling using `Asia/Kolkata`
```python
event = {
    'summary': subject,
    'description': body,
    'start': {'dateTime': start_datetime.isoformat(),
              'timeZone': 'Asia/Kolkata'},
    'end': {'dateTime': end_datetime.isoformat(),
            'timeZone': 'Asia/Kolkata'}
}
```

#### Slack Integration
- **Notification Criteria**:
  - Security alerts
  - Important flagged emails
  - Meeting invitations
```python
def send_slack_message(email_subject, email_body, channel):
    client.chat_postMessage(
        channel=channel,
        text=f"📩 *New Important Email*\n\n*Subject*: {email_subject}"
    )
```

### 5. Development & Testing

#### Development Mode
```python
if os.getenv('DEVELOPMENT_MODE') == 'true':
    # Skip real API calls
    # Use mock data
    # Disable AI features
```

- **Purpose**: 
  - Rapid testing
  - No API costs
  - Offline development

#### Error Handling
```python
try:
    # Operation
except imaplib.IMAP4.error as e:
    logging.error(f"❌ IMAP login failed: {e}")
except Exception as e:
    logging.error(f"❌ Unexpected error: {e}")
finally:
    # Cleanup
```

### 6. Performance Optimizations

#### Parallel Processing
- Email cleaning using ThreadPoolExecutor
- Batch processing for AI operations
```python
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    processed_emails = list(executor.map(cleaner.process_email, emails))
```

#### Caching
- Token caching for OAuth2
- Model caching for HuggingFace
- Response templates for common scenarios

### 7. Security Measures

#### Credential Management
- Environment variables for sensitive data
- Secure token storage
- OAuth2 refresh token handling

#### Data Protection
- Sanitization of email content
- Secure storage of processed data
- Access logging

## Challenges & Solutions

1. **Rate Limiting**
   - **Problem**: Gmail API quotas
   - **Solution**: Implemented batch processing and delays

2. **Memory Usage**
   - **Problem**: Large email attachments
   - **Solution**: Streaming processing and cleanup

3. **Model Performance**
   - **Problem**: Slow inference on CPU
   - **Solution**: Batch processing and model quantization

4. **Authentication**
   - **Problem**: Token expiration
   - **Solution**: Automatic token refresh

5. **Data Consistency**
   - **Problem**: Failed operations
   - **Solution**: Transaction-like processing with rollback

## Future Improvements

1. **Scalability**
   - Implement queue system for processing
   - Add support for multiple email accounts
   - Containerize components

2. **AI Enhancements**
   - Fine-tune models on email data
   - Add more sophisticated reply templates
   - Implement priority prediction

3. **Monitoring**
   - Add performance metrics
   - Implement alert system
   - Create dashboard for monitoring

4. **User Interface**
   - Add web interface
   - Create mobile app
   - Implement user preferences 