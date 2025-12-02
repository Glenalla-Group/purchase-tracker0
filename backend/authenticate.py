"""
Authentication script to set up Gmail API access.

Run this BEFORE starting the server to complete OAuth authentication.
"""

import sys
from pathlib import Path

print("=" * 60)
print("Gmail API Authentication Setup")
print("=" * 60)
print()

# Check for credentials.json
if not Path("credentials.json").exists():
    print("❌ ERROR: credentials.json not found!")
    print()
    print("Please download credentials.json:")
    print("1. Go to https://console.cloud.google.com/apis/credentials")
    print("2. Create OAuth Client ID → Desktop app")
    print("3. Download JSON → Save as credentials.json")
    print()
    sys.exit(1)

print("✓ Found credentials.json")
print()

# Check if already authenticated
if Path("token.json").exists():
    print("✓ Found existing token.json")
    print()
    response = input("Token already exists. Re-authenticate? (y/n): ")
    if response.lower() != 'y':
        print("Using existing authentication. You're all set! ✅")
        sys.exit(0)
    else:
        Path("token.json").unlink()
        print("Deleted old token. Starting fresh authentication...")
        print()

print("Starting OAuth authentication...")
print("A browser window will open shortly...")
print()

try:
    from app.services.gmail_service import GmailService
    
    # This will trigger the OAuth flow
    print("Initializing Gmail service...")
    gmail_service = GmailService()
    
    print()
    print("=" * 60)
    print("✅ Authentication Successful!")
    print("=" * 60)
    print()
    print("token.json has been created and saved.")
    print()
    print("Next steps:")
    print("1. Start the server: python run.py")
    print("2. Test the connection: curl http://localhost:8000/health/gmail")
    print("3. Set up Gmail watch: curl -X POST http://localhost:8000/gmail/watch")
    print()
    
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



