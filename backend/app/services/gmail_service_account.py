"""
Gmail service using Service Account (for Google Workspace domains only).

NOTE: Service accounts can only access Gmail if:
1. You have a Google Workspace account (not regular Gmail)
2. Domain-wide delegation is enabled
3. The service account is authorized by workspace admin

For regular Gmail accounts, you MUST use OAuth 2.0 (gmail_service.py).
"""

import logging
from typing import Any, Dict, List, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import get_settings

logger = logging.getLogger(__name__)

# Required scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify'
]


class GmailServiceAccount:
    """
    Gmail service using Service Account authentication.
    
    WARNING: This only works with Google Workspace accounts where
    domain-wide delegation has been enabled.
    
    For regular Gmail accounts, use the OAuth flow in gmail_service.py
    """
    
    def __init__(self, user_email: str):
        """
        Initialize Gmail service with service account.
        
        Args:
            user_email: The email address to impersonate
        """
        self.settings = get_settings()
        self.user_email = user_email
        self.service = None
        self._authenticate()
    
    def _authenticate(self) -> None:
        """
        Authenticate using service account with domain-wide delegation.
        
        Steps to enable:
        1. Create service account in Google Cloud Console
        2. Download service account key JSON
        3. Enable domain-wide delegation for the service account
        4. In Google Workspace Admin Console:
           - Go to Security → API Controls → Domain-wide Delegation
           - Add the service account client ID
           - Authorize scopes: https://www.googleapis.com/auth/gmail.readonly
        """
        try:
            # Load service account credentials
            credentials = service_account.Credentials.from_service_account_file(
                self.settings.gmail_credentials_path,
                scopes=SCOPES
            )
            
            # Delegate credentials to impersonate user
            delegated_credentials = credentials.with_subject(self.user_email)
            
            # Build the service
            self.service = build('gmail', 'v1', credentials=delegated_credentials)
            logger.info(f"Gmail service initialized for {self.user_email}")
            
        except Exception as e:
            logger.error(f"Failed to authenticate with service account: {e}")
            raise
    
    def get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific email message."""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            return message
        except HttpError as error:
            logger.error(f"Error retrieving message: {error}")
            return None
    
    # Add other methods similar to GmailService...



