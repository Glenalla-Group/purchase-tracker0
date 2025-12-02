"""
Email service for sending emails using SMTP.
Supports Gmail SMTP and other SMTP providers.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service class for sending emails via SMTP."""
    
    def __init__(self):
        """Initialize email service with SMTP configuration."""
        self.settings = get_settings()
        
    def _get_smtp_connection(self):
        """
        Create and return an SMTP connection.
        
        Returns:
            SMTP connection object
        """
        try:
            # Create SMTP connection with TLS
            server = smtplib.SMTP(
                self.settings.smtp_host,
                self.settings.smtp_port
            )
            server.starttls()
            
            # Login to SMTP server
            server.login(
                self.settings.smtp_username,
                self.settings.smtp_password
            )
            
            return server
        except Exception as e:
            logger.error(f"Failed to connect to SMTP server: {e}")
            raise
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        plain_body: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None
    ) -> bool:
        """
        Send an email via SMTP.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML content of the email
            plain_body: Plain text content (optional, falls back to html_body)
            from_email: Sender email (optional, uses configured sender)
            from_name: Sender name (optional, uses configured sender name)
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        try:
            # Set sender information
            sender_email = from_email or self.settings.smtp_from_email
            sender_name = from_name or self.settings.smtp_from_name
            from_address = f"{sender_name} <{sender_email}>"
            
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = from_address
            message["To"] = to_email
            
            # Add plain text version (fallback)
            text_content = plain_body or html_body
            text_part = MIMEText(text_content, "plain")
            message.attach(text_part)
            
            # Add HTML version
            html_part = MIMEText(html_body, "html")
            message.attach(html_part)
            
            # Send email
            with self._get_smtp_connection() as server:
                server.sendmail(sender_email, to_email, message.as_string())
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}", exc_info=True)
            return False
    
    def send_password_reset_email(
        self,
        to_email: str,
        username: str,
        reset_token: str,
        frontend_url: str
    ) -> bool:
        """
        Send a password reset email.
        
        Args:
            to_email: User's email address
            username: User's username
            reset_token: Password reset token
            frontend_url: Frontend URL for constructing reset link
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        reset_link = f"{frontend_url}/reset-password?token={reset_token}"
        
        subject = "Password Reset Request - Purchase Tracker"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px;">
                <h2 style="color: #2563eb; margin-top: 0;">Password Reset Request</h2>
                
                <p>Hello {username},</p>
                
                <p>We received a request to reset your password for your Purchase Tracker account. If you didn't make this request, you can safely ignore this email.</p>
                
                <p>To reset your password, click the button below:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}" 
                       style="background-color: #2563eb; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        Reset Password
                    </a>
                </div>
                
                <p>Or copy and paste this link into your browser:</p>
                <p style="background-color: #e5e7eb; padding: 10px; border-radius: 5px; word-break: break-all;">
                    <a href="{reset_link}" style="color: #2563eb;">{reset_link}</a>
                </p>
                
                <p style="color: #ef4444; font-weight: bold;">⚠️ This link will expire in 1 hour.</p>
                
                <hr style="border: none; border-top: 1px solid #d1d5db; margin: 30px 0;">
                
                <p style="font-size: 12px; color: #6b7280;">
                    If you didn't request a password reset, please ignore this email or contact support if you have concerns.
                </p>
                
                <p style="font-size: 12px; color: #6b7280;">
                    Best regards,<br>
                    The Purchase Tracker Team
                </p>
            </div>
        </body>
        </html>
        """
        
        plain_body = f"""
        Password Reset Request
        
        Hello {username},
        
        We received a request to reset your password for your Purchase Tracker account. 
        If you didn't make this request, you can safely ignore this email.
        
        To reset your password, visit this link:
        {reset_link}
        
        ⚠️ This link will expire in 1 hour.
        
        If you didn't request a password reset, please ignore this email or contact support if you have concerns.
        
        Best regards,
        The Purchase Tracker Team
        """
        
        return self.send_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            plain_body=plain_body
        )

