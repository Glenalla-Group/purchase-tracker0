"""
Authentication script to set up Gmail API access.

Run this BEFORE starting the server to complete OAuth authentication.

Usage:
    python authenticate.py          # Use existing token or create new one
    python authenticate.py --force  # Force re-authentication (delete existing token)
"""

import sys
from pathlib import Path

print("=" * 60)
print("Gmail API Authentication Setup")
print("=" * 60)
print()

# Check for --force flag
force_reauth = "--force" in sys.argv or "-f" in sys.argv

# Get settings (this loads environment from .env files)
from app.config import get_settings

settings = get_settings()

# Get file paths from settings
credentials_path = settings.base_dir / settings.gmail_credentials_path
token_path = settings.base_dir / settings.gmail_token_path

print(f"Environment: {settings.environment}")
print(f"Credentials file: {settings.gmail_credentials_path}")
print(f"Token file: {settings.gmail_token_path}")
print()

# Check for credentials file
if not credentials_path.exists():
    print(f"❌ ERROR: {settings.gmail_credentials_path} not found!")
    print()
    print("Please download credentials from Google Cloud Console:")
    print("1. Go to https://console.cloud.google.com/apis/credentials")
    print("2. Create OAuth Client ID → Desktop app")
    print("3. Download JSON → Save as:", settings.gmail_credentials_path)
    print()
    sys.exit(1)

print(f"✓ Found {settings.gmail_credentials_path}")
print()

# Check if already authenticated
if token_path.exists():
    print(f"✓ Found existing {settings.gmail_token_path}")
    print()
    
    if force_reauth:
        token_path.unlink()
        print(f"🔄 Force flag detected - deleted old {settings.gmail_token_path}")
        print("Starting fresh authentication...")
        print()
    else:
        try:
            response = input("Token already exists. Re-authenticate? (y/n): ")
            if response.lower() != 'y':
                print("Using existing authentication. You're all set! ✅")
                print()
                print("Tip: Run 'python authenticate.py --force' to re-authenticate without prompting")
                sys.exit(0)
            else:
                token_path.unlink()
                print(f"Deleted old {settings.gmail_token_path}. Starting fresh authentication...")
                print()
        except (EOFError, KeyboardInterrupt):
            print()
            print("⚠ Cannot prompt for input in this environment.")
            print("Using existing authentication. You're all set! ✅")
            print()
            print("Tip: Run 'python authenticate.py --force' to re-authenticate without prompting")
            sys.exit(0)

print("Starting OAuth authentication...")
print("🌐 A browser window should open shortly...")
print("   If it doesn't, check for errors below.")
print()

try:
    from app.services.gmail_service import GmailService
    
    # This will trigger the OAuth flow
    print("Initializing Gmail service...")
    print()
    
    gmail_service = GmailService()
    
    # Verify token was created
    if not token_path.exists():
        print()
        print("⚠ WARNING: Authentication completed but token file not found!")
        print(f"   Expected: {settings.gmail_token_path}")
        sys.exit(1)
    
    # Test the connection
    print()
    print("Testing Gmail API connection...")
    if gmail_service.test_connection():
        print()
        print("=" * 60)
        print("✅ Authentication Successful!")
        print("=" * 60)
        print()
        print(f"✓ {settings.gmail_token_path} has been created and saved.")
        print()
        print("Next steps:")
        print("1. Start the server: python run.py")
        print("2. Test the connection: curl http://localhost:8000/health/gmail")
        print("3. Set up Gmail watch: curl -X POST http://localhost:8000/gmail/watch")
        print()
    else:
        print()
        print("⚠ WARNING: Token created but connection test failed!")
        print("   You may need to re-authenticate or check your credentials.")
        print()
        sys.exit(1)
    
except FileNotFoundError as e:
    print()
    print(f"❌ ERROR: {e}")
    print()
    sys.exit(1)
    
except Exception as e:
    print()
    print(f"❌ ERROR during authentication: {e}")
    print()
    print("Common issues:")
    print("- Make sure you downloaded 'Desktop app' credentials (not Web)")
    print("- Check that Gmail API is enabled in Cloud Console")
    print("- Verify you added yourself as a test user in OAuth consent screen")
    print()
    sys.exit(1)



