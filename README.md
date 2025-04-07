# Email Processing Pipeline

An automated email processing system that fetches, cleans, and analyzes emails from Gmail, with support for meeting scheduling, automated replies, and intelligent notifications.

## Architecture Overview

```mermaid
graph TD
    A[Gmail Inbox] -->|OAuth2| B[Gmail Fetcher]
    B -->|Raw Emails| C[Email Cleaner]
    C -->|Cleaned Text| D[Email Processor]
    D -->|Text| E[AI Models]
    E -->|Results| D
    D -->|Events| F[Google Calendar]
    D -->|Notifications| G[Slack]
    D -->|Replies| H[Reply Manager]
    H -->|Send| A
    I[(Database)] <-->|Store/Retrieve| D
```

### Component Interactions

1. **Email Flow**:
   - Gmail Fetcher connects to Gmail via OAuth2
   - Fetches new emails periodically (every 5 minutes)
   - Saves raw emails to `data/raw/emails.json`

2. **Processing Pipeline**:
   - Email Cleaner normalizes and sanitizes email content
   - Removes signatures, forwarded content, and formatting
   - Extracts key information (dates, times, requests)

3. **AI Processing**:
   - Uses HuggingFace models for:
     - Text summarization (T5-small)
     - Intent classification (DistilRoBERTa)
     - Reply generation (GPT-2)
   - Performs semantic search for relevant information

4. **Actions**:
   - Creates calendar events for detected meetings
   - Sends Slack notifications for important emails
   - Generates and sends contextual replies
   - Stores processed data in `data/processed/`

## Setup Instructions

### 1. Clone and Install
```bash
git clone <repository-url>
cd email-processor
pip install -r project_files/requirements.txt
```

### 2. API Credentials Setup

#### Gmail API
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable Gmail and Calendar APIs
4. Create OAuth2 credentials:
   - Download as `credentials.json`
   - Place in `configuration/credentials.json`
5. Create Service Account:
   - Download as `service_account.json`
   - Place in `configuration/service_account.json`

#### Slack Integration
1. Go to [Slack API](https://api.slack.com/apps)
2. Create a new app
3. Enable Bot Token Scopes:
   - `chat:write`
   - `channels:read`
4. Install app to workspace
5. Copy Bot User OAuth Token

#### HuggingFace
1. Create account on [HuggingFace](https://huggingface.co)
2. Generate API token
3. Note the token for configuration

### 3. Environment Configuration
Create `configuration/.env` with:
```env
# Gmail Credentials
GMAIL_USER=your.email@gmail.com
GMAIL_APP_PASSWORD=your_app_password

# AI and Integration Features
HUGGINGFACE_TOKEN=your_token
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_CHANNEL=your-channel
GOOGLE_API_KEY=your_api_key
SEARCH_ENGINE_ID=your_search_engine_id

# Optional Development Mode
DEVELOPMENT_MODE=false
```

## Usage

### Running the Assistant

1. **Production Mode**:
```bash
python src/run_all.py
```

2. **Development Mode** (uses mock data, no real API calls):
```bash
$env:DEVELOPMENT_MODE='true'; python src/run_all.py
```

### Stopping the Assistant
Two methods:
1. Press `Ctrl+C` in the terminal
2. Create stop file: `echo $null > stop.txt`

### Example Output
```
🔄 Starting email pipeline service...
✅ Environment check passed
✅ Successfully authenticated with Gmail
🔄 Step 1: Fetching emails...
✅ Fetched 4 new emails
🔄 Step 2: Cleaning emails...
✅ Emails cleaned successfully
🔄 Step 3: Processing emails...
📩 From: sender@example.com
📝 Summary: Meeting request for project discussion
📅 Created calendar event
🤖 Generated and sent reply
💬 Slack notification sent
✅ Email pipeline completed in 4.30 seconds!
```
## Directory Structure

```
project_root/
├── README.md              # Project documentation
├── .gitignore            # Git ignore rules
├── src/                    # Source code
│   ├── core/              # Core functionality modules
│   │   ├── email_cleaner.py
│   │   ├── gmail_fetcher.py
│   │   └── update.py
│   ├── services/          # External services integration
│   │   ├── gmail_auth.py
│   │   └── reply_manager.py
│   ├── database/          # Database operations
│   │   └── database.py
│   ├── security/          # Security-related code
│   ├── utils/             # Utility functions
│   └── run_all.py         # Main script
├── data/                   # Data storage
│   ├── raw/               # Raw email data
│   │   └── emails.json    # Current raw emails
│   └── processed/         # Processed email data
│       └── processed_emails.json
├── logs/                   # Log files
│   └── email_pipeline.log
├── emails/                # Email backups
│   └── YYYY-MM-DD/       # Date-based backup folders
├── configuration/         # Configuration files
│   ├── .env              # Environment variables
│   ├── credentials.json  # Google OAuth2 credentials
│   ├── service_account.json # Google service account
│   └── token.json        # OAuth2 token cache
└── project_files/        # Project configuration files
    ├── requirements.txt
    ├── setup.py
    └── DOCUMENTATION.md  # Detailed project documentation
```

## Features

### Email Processing
- Automatic email fetching and cleaning
- Smart meeting detection and calendar integration
- AI-powered email summarization
- Intent classification
- Automated reply generation

### Integrations
- Gmail API for email operations
- Google Calendar for scheduling
- Slack for notifications
- HuggingFace for AI models

### Security
- Secure credential storage
- Environment variable management
- OAuth2 authentication
- Development mode for testing

### Data Management
- JSON-based data storage
- Automatic email backups
- Detailed logging
- Clean directory structure

## Development

### Running Tests
```bash
python -m pytest tests/
```

### Development Mode
Set `DEVELOPMENT_MODE=true` in `.env` to:
- Skip real API calls
- Use mock data
- Test functionality safely

### Adding New Features
1. Create new module in appropriate directory
2. Update `run_all.py` to include new functionality
3. Add configuration in `.env` if needed
4. Update tests and documentation

## Troubleshooting

### Common Issues
1. **Authentication Errors**:
   - Check credentials in `configuration/`
   - Verify `.env` variables
   - Ensure OAuth2 flow completed

2. **API Rate Limits**:
   - Adjust fetch frequency
   - Handle quota errors gracefully

3. **Missing Dependencies**:
   - Run `pip install -r requirements.txt`
   - Check Python version (3.8+ required)

### Logs
- Check `logs/email_pipeline.log` for detailed logs
- Enable debug logging in `.env`

## Contributing
1. Fork the repository
2. Create feature branch
3. Submit pull request
4. Ensure tests pass

## License
MIT License - See LICENSE file for details
