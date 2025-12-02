# Purchase Tracker Backend

A production-ready FastAPI backend that monitors Gmail inbox using Google Cloud Pub/Sub and extracts purchase information from emails using BeautifulSoup.

## Features

- 📧 **Gmail Integration**: Monitor Gmail inbox in real-time using Gmail API
- 🔔 **Push Notifications**: Receive instant notifications via Google Cloud Pub/Sub
- 🔍 **HTML Parsing**: Extract structured data from email HTML using BeautifulSoup
- 🚀 **FastAPI Framework**: Modern, fast, and well-documented API
- 📦 **Structured Architecture**: Clean code organization for easy maintenance and expansion
- 🔐 **OAuth2 Authentication**: Secure Gmail API access
- 📊 **Auto-generated API Docs**: Interactive API documentation with Swagger UI

## Architecture

```
purchase-tracker-backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── api/                 # API endpoints
│   │   ├── __init__.py
│   │   ├── webhook.py       # Pub/Sub webhook endpoint
│   │   └── health.py        # Health check endpoints
│   ├── config/              # Configuration management
│   │   ├── __init__.py
│   │   └── settings.py      # Environment settings
│   ├── models/              # Pydantic models
│   │   ├── __init__.py
│   │   └── email.py         # Email data models
│   └── services/            # Business logic
│       ├── __init__.py
│       ├── gmail_service.py # Gmail API integration
│       └── email_parser.py  # BeautifulSoup parsing
├── requirements.txt         # Python dependencies
├── .gitignore
├── .env                     # Environment variables (create this)
└── run.py                   # Application runner
```

## Prerequisites

- Python 3.10 or higher
- Google Cloud Project with Gmail API enabled
- Google Cloud Pub/Sub configured

## Setup Instructions

### 1. Clone and Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Google Cloud Setup

#### A. Enable APIs

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the following APIs:
   - Gmail API
   - Cloud Pub/Sub API

#### B. Create OAuth2 Credentials

1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth client ID**
3. Choose **Desktop app** as application type
4. Download the credentials JSON file
5. Save it as `credentials.json` in the project root

#### C. Set Up Pub/Sub

1. Go to **Pub/Sub** in Google Cloud Console
2. Create a topic (e.g., `gmail-notifications`)
3. Create a subscription for the topic (e.g., `gmail-sub`)
4. Grant Gmail permissions to publish to the topic:
   - Go to topic **Permissions**
   - Add member: `gmail-api-push@system.gserviceaccount.com`
   - Role: **Pub/Sub Publisher**

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=True

# Google Cloud Project
GOOGLE_CLOUD_PROJECT_ID=your-project-id
GOOGLE_PUBSUB_TOPIC=projects/your-project-id/topics/gmail-notifications
GOOGLE_PUBSUB_SUBSCRIPTION=projects/your-project-id/subscriptions/gmail-sub

# Gmail API Configuration
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_TOKEN_PATH=token.json
GMAIL_SCOPES=https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.modify

# Webhook Configuration
WEBHOOK_SECRET=your-webhook-secret-key

# Application Settings
LOG_LEVEL=INFO
```

### 4. First-Time Authentication

Run the application for the first time to authenticate with Gmail:

```bash
python run.py
```

This will:
1. Open a browser window for Google OAuth2 authentication
2. Ask you to grant permissions to access Gmail
3. Save the token to `token.json` for future use

### 5. Deploy Webhook (Production)

For Pub/Sub to send notifications, your webhook endpoint must be publicly accessible:

#### Option A: Deploy to Cloud (Recommended)

Deploy to Google Cloud Run, AWS, or any cloud provider:

```bash
# Example: Google Cloud Run
gcloud run deploy purchase-tracker \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

#### Option B: Use ngrok for Testing

```bash
# Install ngrok: https://ngrok.com/
ngrok http 8000

# Copy the HTTPS URL provided by ngrok
```

### 6. Configure Gmail Push Notifications

Once your webhook is publicly accessible, set up Gmail watch:

```bash
# Using the API endpoint
curl -X POST http://your-domain.com/gmail/watch
```

Or use the FastAPI docs interface at `http://your-domain.com/docs`

## Usage

### Running the Application

```bash
python run.py
```

The server will start at `http://localhost:8000`

### API Endpoints

#### Health Check
```bash
GET /health
GET /health/gmail
```

#### Root
```bash
GET /
```

#### Authentication (for Admin Frontend)
```bash
POST /auth/signin          # User login
GET /auth/logout           # User logout
POST /auth/refresh         # Refresh access token
GET /auth/user/{user_id}   # Get user info
```

**Test Credentials:**
- Username: `admin` / Password: `demo1234`
- Username: `user` / Password: `demo1234`

#### Gmail Watch Management
```bash
POST /gmail/watch        # Set up push notifications
POST /gmail/stop-watch   # Stop push notifications
```

#### Webhook (Called by Pub/Sub)
```bash
POST /api/gmail/webhook  # Receives Gmail notifications
```

#### Testing
```bash
POST /api/gmail/test     # Manually process latest emails
```

### API Documentation

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Email Processing Flow

1. **New Email Arrives** → Gmail sends notification to Pub/Sub
2. **Pub/Sub Triggers Webhook** → POST request to `/api/gmail/webhook`
3. **Fetch Email** → Backend uses Gmail API to retrieve email content
4. **Parse HTML** → BeautifulSoup extracts information from HTML
5. **Process Data** → Extracted info is logged/stored (customize as needed)

## Customization

### Modify Email Parsing Logic

Edit `app/services/email_parser.py` to customize extraction logic:

```python
def _extract_purchase_info(self, soup: BeautifulSoup, extracted_info: ExtractedInfo) -> None:
    # Add your custom extraction patterns here
    # Example: Extract specific merchant data
    merchant_element = soup.find('div', class_='merchant-name')
    if merchant_element:
        extracted_info.merchant = merchant_element.get_text(strip=True)
```

### Add Custom CSS Selectors

Use the `extract_custom_data` method for flexible extraction:

```python
selectors = {
    'order_id': '#order-number',
    'total': '.total-amount',
    'tracking': 'a[href*="tracking"]'
}
extracted = email_parser.extract_custom_data(html_content, selectors)
```

### Store Extracted Data

Add database integration in `app/api/webhook.py`:

```python
async def process_email_notification(message_id: str) -> None:
    # ... existing code ...
    
    if extracted_info.extraction_successful:
        # Add your storage logic here
        # Example: await database.save(extracted_info)
        pass
```

## Testing

### Test Email Processing Without Pub/Sub

```bash
curl -X POST http://localhost:8000/api/gmail/test
```

This will fetch and process the 5 most recent emails.

### Test Individual Components

```python
# Test Gmail service
from app.services.gmail_service import GmailService

service = GmailService()
messages = service.list_messages(max_results=5)
print(messages)

# Test email parser
from app.services.email_parser import EmailParser

parser = EmailParser()
extracted = parser.parse_email(email_data)
print(extracted)
```

## Monitoring and Logs

Logs are written to:
- Console (stdout)
- `app.log` file

Log levels can be configured in `.env`:
```env
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## Security Considerations

1. **Credentials**: Never commit `credentials.json` or `token.json` to version control
2. **Environment Variables**: Use proper secret management in production
3. **CORS**: Configure `allow_origins` appropriately in `app/main.py`
4. **Webhook Secret**: Add signature verification for Pub/Sub messages in production
5. **HTTPS**: Always use HTTPS in production for webhook endpoint

## Troubleshooting

### "Credentials file not found"
- Ensure `credentials.json` is in the project root
- Download it from Google Cloud Console → APIs & Services → Credentials

### "Token expired"
- Delete `token.json` and restart the application
- Re-authenticate when prompted

### "Pub/Sub not receiving messages"
- Verify Gmail watch is active: `POST /gmail/watch`
- Check Pub/Sub topic permissions
- Ensure webhook URL is publicly accessible
- Check Cloud Logging for Pub/Sub delivery errors

### "BeautifulSoup not finding elements"
- Inspect email HTML structure
- Update CSS selectors in `email_parser.py`
- Use the test endpoint to debug extraction

## Expanding the Application

### Add Database Storage

```bash
# Install database driver
pip install sqlalchemy asyncpg

# Create models and integrate
```

### Add Email Classification

```bash
# Install ML library
pip install scikit-learn

# Add classification service
```

### Add Webhooks for Notifications

```bash
# Install HTTP client
pip install httpx

# Add webhook service to notify external systems
```

### Add Frontend Dashboard

```bash
# Create React/Vue frontend
# Connect to FastAPI endpoints
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - feel free to use this project for any purpose.

## Support

For issues and questions:
- Check the troubleshooting section
- Review FastAPI documentation: https://fastapi.tiangolo.com/
- Review Gmail API documentation: https://developers.google.com/gmail/api

## Acknowledgments

- FastAPI for the excellent web framework
- BeautifulSoup for HTML parsing
- Google Cloud Platform for Gmail and Pub/Sub APIs



# CI/CD is automated