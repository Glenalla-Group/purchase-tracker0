"""
Gmail API service for interacting with Gmail.
"""

import base64
import logging
import os.path
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import get_settings
from app.models.email import EmailData

logger = logging.getLogger(__name__)


class GmailService:
    """Service class for Gmail API operations."""
    
    def __init__(self):
        """Initialize Gmail service with authentication."""
        self.settings = get_settings()
        self.creds: Optional[Credentials] = None
        self.service = None
        self._authenticate()
    
    def _authenticate(self) -> None:
        """
        Authenticate with Gmail API using OAuth2.
        
        This method will:
        1. Load existing token if available
        2. Refresh token if expired
        3. Run OAuth flow if no valid credentials exist
        """
        token_path = self.settings.base_dir / self.settings.gmail_token_path
        credentials_path = self.settings.base_dir / self.settings.gmail_credentials_path
        
        # Load token if it exists
        if token_path.exists():
            self.creds = Credentials.from_authorized_user_file(
                str(token_path), 
                self.settings.gmail_scopes_list
            )
        
        # If credentials are invalid or don't exist, authenticate
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                logger.info("Refreshing expired credentials")
                self.creds.refresh(Request())
            else:
                if not credentials_path.exists():
                    raise FileNotFoundError(
                        f"Credentials file not found at {credentials_path}. "
                        "Please download credentials.json from Google Cloud Console."
                    )
                
                logger.info("Running OAuth flow for new credentials")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), 
                    self.settings.gmail_scopes_list
                )
                self.creds = flow.run_local_server(port=0)
            
            # Save credentials for future use
            with open(token_path, 'w') as token:
                token.write(self.creds.to_json())
            logger.info(f"Credentials saved to {token_path}")
        
        # Build the service
        self.service = build('gmail', 'v1', credentials=self.creds)
        logger.debug("Gmail service initialized successfully")
    
    def get_message(self, message_id: str, format: str = 'full') -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific email message.
        
        Args:
            message_id: The ID of the message to retrieve
            format: The format of the message ('full', 'raw', 'metadata', 'minimal')
        
        Returns:
            Dictionary containing message data or None if error
        """
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format=format
            ).execute()
            logger.info(f"Successfully retrieved message {message_id}")
            return message
        except HttpError as error:
            logger.error(f"Error retrieving message {message_id}: {error}")
            return None
    
    def parse_message_to_email_data(self, message: Dict[str, Any]) -> EmailData:
        """
        Parse Gmail API message format to EmailData model.
        
        Args:
            message: Raw message data from Gmail API
        
        Returns:
            EmailData object with parsed information
        """
        headers = {
            header['name']: header['value'] 
            for header in message.get('payload', {}).get('headers', [])
        }
        
        # Extract HTML and text content
        html_content = self._extract_html_content(message.get('payload', {}))
        text_content = self._extract_text_content(message.get('payload', {}))
        
        return EmailData(
            message_id=message['id'],
            thread_id=message['threadId'],
            history_id=message.get('historyId'),
            subject=headers.get('Subject', 'No Subject'),
            sender=headers.get('From', ''),
            to=headers.get('To', '').split(',') if headers.get('To') else [],
            cc=headers.get('Cc', '').split(',') if headers.get('Cc') else [],
            date=headers.get('Date'),
            html_content=html_content,
            text_content=text_content,
            snippet=message.get('snippet'),
            labels=message.get('labelIds', [])
        )
    
    def _extract_html_content(self, payload: Dict[str, Any]) -> Optional[str]:
        """
        Extract HTML content from message payload.
        
        Args:
            payload: Message payload from Gmail API
        
        Returns:
            Decoded HTML content or None
        """
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/html':
                    data = part.get('body', {}).get('data')
                    if data:
                        return base64.urlsafe_b64decode(data).decode('utf-8')
                
                # Check nested parts (multipart messages)
                if 'parts' in part:
                    html = self._extract_html_content(part)
                    if html:
                        return html
        
        # Check direct body
        if payload.get('mimeType') == 'text/html':
            data = payload.get('body', {}).get('data')
            if data:
                return base64.urlsafe_b64decode(data).decode('utf-8')
        
        return None
    
    def _extract_text_content(self, payload: Dict[str, Any]) -> Optional[str]:
        """
        Extract plain text content from message payload.
        
        Args:
            payload: Message payload from Gmail API
        
        Returns:
            Decoded text content or None
        """
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part.get('body', {}).get('data')
                    if data:
                        return base64.urlsafe_b64decode(data).decode('utf-8')
                
                # Check nested parts
                if 'parts' in part:
                    text = self._extract_text_content(part)
                    if text:
                        return text
        
        # Check direct body
        if payload.get('mimeType') == 'text/plain':
            data = payload.get('body', {}).get('data')
            if data:
                return base64.urlsafe_b64decode(data).decode('utf-8')
        
        return None
    
    def list_messages(
        self, 
        max_results: int = 10, 
        query: str = "",
        label_ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        List message IDs from inbox.
        
        Args:
            max_results: Maximum number of messages to return
            query: Gmail search query
            label_ids: Only return messages with these labels
        
        Returns:
            List of message IDs
        """
        try:
            results = self.service.users().messages().list(
                userId='me',
                maxResults=max_results,
                q=query,
                labelIds=label_ids or ['INBOX']
            ).execute()
            
            messages = results.get('messages', [])
            message_ids = [msg['id'] for msg in messages]
            logger.debug(f"Listed {len(message_ids)} messages")
            return message_ids
        except HttpError as error:
            logger.error(f"Error listing messages: {error}")
            return []
    
    def watch_inbox(self, topic_name: str) -> Dict[str, Any]:
        """
        Set up push notifications for inbox changes.
        
        Args:
            topic_name: Full Pub/Sub topic name (projects/{project}/topics/{topic})
        
        Returns:
            Watch response with historyId and expiration
        """
        try:
            request = {
                'topicName': topic_name,
                'labelIds': ['INBOX']
            }
            
            result = self.service.users().watch(
                userId='me',
                body=request
            ).execute()
            
            logger.info(f"Watch set up successfully. History ID: {result.get('historyId')}")
            return result
        except HttpError as error:
            logger.error(f"Error setting up watch: {error}")
            raise
    
    def stop_watch(self) -> None:
        """Stop push notifications."""
        try:
            self.service.users().stop(userId='me').execute()
            logger.info("Watch stopped successfully")
        except HttpError as error:
            logger.error(f"Error stopping watch: {error}")
    
    def get_or_create_label(self, label_name: str) -> Optional[Dict[str, Any]]:
        """
        Get or create a Gmail label.
        
        Args:
            label_name: Name of the label (can include "/" for nested labels)
        
        Returns:
            Label dictionary with 'id' and 'name' keys, or None if failed
        """
        try:
            # List all labels
            results = self.service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])
            
            # Check if label exists
            for label in labels:
                if label['name'] == label_name:
                    logger.debug(f"Label '{label_name}' already exists")
                    return label
            
            # Create label if it doesn't exist
            logger.info(f"Creating label: {label_name}")
            label_object = {
                'name': label_name,
                'messageListVisibility': 'show',
                'labelListVisibility': 'labelShow'
            }
            
            created_label = self.service.users().labels().create(
                userId='me',
                body=label_object
            ).execute()
            
            logger.info(f"Created label: {label_name} (ID: {created_label['id']})")
            return created_label
        
        except HttpError as error:
            logger.error(f"Error creating/getting label '{label_name}': {error}")
            return None
    
    def add_label_to_message(self, message_id: str, label_id: str) -> bool:
        """
        Add a label to a Gmail message.
        
        Args:
            message_id: Gmail message ID
            label_id: Label ID to add
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': [label_id]}
            ).execute()
            
            logger.debug(f"Added label {label_id} to message {message_id}")
            return True
        
        except HttpError as error:
            logger.error(f"Error adding label to message: {error}")
            return False
    
    def list_messages_with_query(
        self,
        query: str,
        max_results: int = 10,
        exclude_label: Optional[str] = None
    ) -> List[str]:
        """
        List message IDs matching a Gmail search query.
        
        Args:
            query: Gmail search query (e.g., "from:example@example.com subject:test")
            max_results: Maximum number of messages to return
            exclude_label: Optional label name to exclude (e.g., "PrepWorx/Processed")
        
        Returns:
            List of message IDs
        """
        try:
            # If exclude_label is provided, add it to query
            if exclude_label:
                query = f"{query} -label:{exclude_label}"
            
            logger.info(f"Searching Gmail with query: {query}")
            
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            message_ids = [msg['id'] for msg in messages]
            
            logger.info(f"Found {len(message_ids)} messages matching query")
            return message_ids
        
        except HttpError as error:
            logger.error(f"Error searching messages: {error}")
            return []

