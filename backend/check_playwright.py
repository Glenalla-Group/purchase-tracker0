#!/usr/bin/env python3
"""
Quick script to check if Playwright is properly installed
"""

import sys

def check_playwright():
    """Check Playwright installation"""
    print("=" * 60)
    print("Playwright Installation Check")
    print("=" * 60)
    print()
    
    # Check Python package
    print("1. Checking Playwright Python package...")
    try:
        import playwright
        # Try to get version from package metadata (Python 3.8+)
        try:
            import importlib.metadata
            version = importlib.metadata.version('playwright')
            print(f"   ✅ Playwright package installed (version: {version})")
        except (ImportError, importlib.metadata.PackageNotFoundError):
            # Fallback: just confirm it's installed
            print("   ✅ Playwright package installed")
    except ImportError:
        print("   ❌ Playwright package NOT installed")
        print("   Run: pip install playwright")
        return False
    
    # Check browsers
    print("\n2. Checking Playwright browsers...")
    try:
        from playwright.sync_api import sync_playwright
        print("   Attempting to initialize Playwright...")
        
        # Direct initialization (no threading to avoid cross-thread issues)
        try:
            pw = sync_playwright().start()
            print("   ✅ Playwright initialized successfully")
            
            # Check if chromium is available
            try:
                browser_type = pw.chromium
                print("   ✅ Chromium browser type available")
                
                # Try to actually launch a browser (this verifies the binary exists)
                print("   Testing browser launch...")
                browser = browser_type.launch(headless=True)
                print("   ✅ Chromium browser launched successfully")
                browser.close()
                pw.stop()
                print("   ✅ All checks passed!")
                return True
            except Exception as e:
                print(f"   ❌ Chromium browser issue: {e}")
                print("   Run: playwright install chromium")
                try:
                    pw.stop()
                except:
                    pass
                return False
                
        except FileNotFoundError as e:
            print("   ❌ Playwright browsers not installed")
            print("   Run: playwright install chromium")
            return False
        except Exception as e:
            print(f"   ❌ Error initializing Playwright: {e}")
            print("   Run: playwright install chromium")
            return False
        
    except ImportError:
        print("   ❌ Playwright sync_api not available")
        print("   Run: pip install playwright")
        return False
    except Exception as e:
        print(f"   ❌ Error checking browsers: {e}")
        print("   Run: playwright install chromium")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All checks passed! Playwright is ready to use.")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = check_playwright()
    sys.exit(0 if success else 1)

