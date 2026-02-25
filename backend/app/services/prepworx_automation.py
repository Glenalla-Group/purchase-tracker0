"""
PrepWorx Automation Service
Handles automation of inbound creation in PrepWorx platform using Selenium
"""

import logging
from typing import List, Dict, Any, Optional
import time
import os
from pathlib import Path
from app.config import get_settings

logger = logging.getLogger(__name__)

# Get project root directory (backend folder)
PROJECT_ROOT = Path(__file__).parent.parent.parent
SCREENSHOT_DIR = PROJECT_ROOT / "tmp"
SCREENSHOT_DIR.mkdir(exist_ok=True)  # Create tmp directory if it doesn't exist

# Try to import Selenium, but handle gracefully if not installed
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.warning("Selenium not installed. Please run: pip install selenium")


class PrepWorxCredentials:
    """PrepWorx account credentials based on address - loaded from settings"""
    
    @classmethod
    def get_credentials_by_address(cls, address: str) -> Optional[Dict[str, str]]:
        """Get credentials based on shipping address from settings"""
        if not address:
            return None
            
        # Get settings instance
        settings = get_settings()
        address_lower = address.lower()
        
        # 595 Lloyd Lane credentials
        if "595 lloyd lane" in address_lower:
            email = settings.prepworx_lloyd_lane_email
            password = settings.prepworx_lloyd_lane_password
            
            if not email or not password:
                logger.error("PREPWORX_LLOYD_LANE_EMAIL and PREPWORX_LLOYD_LANE_PASSWORD must be set in .env file")
                return None
                
            return {
                "email": email,
                "password": password,
                "address": "595 Lloyd Lane"
            }
        
        # 2025 Vista Ave credentials
        elif "2025 vista ave" in address_lower:
            email = settings.prepworx_vista_ave_email
            password = settings.prepworx_vista_ave_password
            
            if not email or not password:
                logger.error("PREPWORX_VISTA_AVE_EMAIL and PREPWORX_VISTA_AVE_PASSWORD must be set in .env file")
                return None
                
            return {
                "email": email,
                "password": password,
                "address": "2025 Vista Ave"
            }
        else:
            return None


class PrepWorxAutomation:
    """Automates inbound creation in PrepWorx platform"""
    
    PREPWORX_URL = "https://app.prepworx.io/"
    LOGIN_TIMEOUT = 30  # 30 seconds
    
    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        
    def __enter__(self):
        """Context manager entry"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup"""
        self.close()
        
    def check_selenium_installation(self) -> tuple[bool, str]:
        """
        Check if Selenium is properly installed
        
        Returns:
            (is_installed, error_message)
        """
        if not SELENIUM_AVAILABLE:
            return False, "Selenium Python package not installed. Run: pip install selenium"
        
        try:
            # Check if chromedriver is available
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.service import utils
            
            # Try to find chromedriver in PATH
            try:
                service = Service()
                return True, ""
            except Exception as e:
                return False, f"ChromeDriver not found. Make sure Chrome and ChromeDriver are installed. Error: {str(e)}"
        except Exception as e:
            return False, f"Error checking Selenium installation: {str(e)}"
    
    def start_browser(self, headless: bool = True):
        """Start Selenium Chrome browser"""
        if not SELENIUM_AVAILABLE:
            logger.error("Selenium not available. Please install: pip install selenium")
            return False
        
        try:
            logger.info(f"Starting Selenium Chrome browser (headless={headless})...")
            
            logger.info("Step 1/3: Setting up Chrome options...")
            # Set up Chrome options
            chrome_options = ChromeOptions()
            
            if headless:
                chrome_options.add_argument('--headless=new')  # Use new headless mode
                chrome_options.add_argument('--disable-gpu')
                os.environ.setdefault('DISPLAY', ':99')
                os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE', '1')
            
            # Add common arguments for stability
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-setuid-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--window-size=1920,1080')
            
            # Set download preferences - download to tmp folder
            download_dir = str(SCREENSHOT_DIR)  # Use tmp folder for downloads
            prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # Disable automation flags
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            logger.info("✅ Step 1/3: Chrome options configured")
            
            logger.info("Step 2/3: Initializing Chrome WebDriver...")
            try:
                # Initialize Chrome driver
                self.driver = webdriver.Chrome(options=chrome_options)
                
                # Set implicit wait
                self.driver.implicitly_wait(10)
                
                # Initialize WebDriverWait
                self.wait = WebDriverWait(self.driver, self.LOGIN_TIMEOUT)
                
                logger.info("✅ Step 2/3: Chrome WebDriver initialized successfully")
            except WebDriverException as e:
                logger.error(f"❌ Failed to initialize Chrome WebDriver: {e}")
                logger.error("Make sure Chrome and ChromeDriver are installed and compatible versions")
                return False
            except Exception as e:
                logger.error(f"❌ Failed to initialize WebDriver: {e}", exc_info=True)
                return False
            
            logger.info("✅ Step 3/3: Browser started successfully - ready to use!")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start browser: {e}", exc_info=True)
            self.close()
            return False
            
    def close(self):
        """Close browser and cleanup"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
                self.wait = None
                
            logger.info("Browser closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
    
    def _find_element_by_multiple_selectors(self, selectors: List[tuple], timeout: int = 5) -> Optional[Any]:
        """
        Helper method to find element by trying multiple selectors
        
        Args:
            selectors: List of (By, selector) tuples
            timeout: Timeout for each selector attempt
            
        Returns:
            WebElement if found, None otherwise
        """
        for by, selector in selectors:
            try:
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by, selector))
                )
                if element:
                    return element
            except:
                continue
        return None
            
    def login(self, email: str, password: str, take_screenshots: bool = False) -> bool:
        """
        Login to PrepWorx platform
        
        Args:
            email: User email
            password: User password
            take_screenshots: Whether to take screenshots during login (for debugging)
            
        Returns:
            True if login successful, False otherwise
        """
        if not self.driver:
            logger.error("Browser not started. Call start_browser() first.")
            return False
            
        try:
            logger.info(f"🌐 Navigating to PrepWorx: {self.PREPWORX_URL}")
            self.driver.get(self.PREPWORX_URL)
            
            if take_screenshots:
                try:
                    screenshot_path = str(SCREENSHOT_DIR / "prepworx_login_1_initial.png")
                    self.driver.save_screenshot(screenshot_path)
                    logger.info(f"📸 Screenshot saved: {screenshot_path}")
                except Exception as e:
                    logger.warning(f"Could not take screenshot: {e}")
            
            logger.info(f"🔐 Attempting login with email: {email}")
            
            # Wait for the page to load
            logger.info("⏳ Waiting for page to load...")
            time.sleep(2)
            
            # Look for email input field (common selectors)
            email_selectors = [
                (By.CSS_SELECTOR, 'input[type="email"]'),
                (By.NAME, 'email'),
                (By.ID, 'email'),
                (By.CSS_SELECTOR, 'input[placeholder*="email" i]'),
                (By.CSS_SELECTOR, 'input[placeholder*="Email" i]')
            ]
            
            email_input = None
            for by, selector in email_selectors:
                try:
                    email_input = self.wait.until(
                        EC.presence_of_element_located((by, selector))
                    )
                    if email_input:
                        logger.info(f"Found email input with selector: {selector}")
                        break
                except:
                    continue
                    
            if not email_input:
                logger.error("Could not find email input field")
                return False
                
            # Fill email
            logger.info("✍️  Filling email field...")
            email_input.clear()
            email_input.send_keys(email)
            logger.info("✅ Email filled")
            
            if take_screenshots:
                try:
                    screenshot_path = str(SCREENSHOT_DIR / "prepworx_login_2_email_filled.png")
                    self.driver.save_screenshot(screenshot_path)
                    logger.info(f"📸 Screenshot saved: {screenshot_path}")
                except Exception as e:
                    logger.warning(f"Could not take screenshot: {e}")
            
            # Look for password input field
            password_selectors = [
                (By.CSS_SELECTOR, 'input[type="password"]'),
                (By.NAME, 'password'),
                (By.ID, 'password')
            ]
            
            password_input = None
            for by, selector in password_selectors:
                try:
                    password_input = self.wait.until(
                        EC.presence_of_element_located((by, selector))
                    )
                    if password_input:
                        logger.info(f"Found password input with selector: {selector}")
                        break
                except:
                    continue
                    
            if not password_input:
                logger.error("Could not find password input field")
                return False
                
            # Fill password
            logger.info("✍️  Filling password field...")
            password_input.clear()
            password_input.send_keys(password)
            logger.info("✅ Password filled")
            
            if take_screenshots:
                try:
                    screenshot_path = str(SCREENSHOT_DIR / "prepworx_login_3_password_filled.png")
                    self.driver.save_screenshot(screenshot_path)
                    logger.info(f"📸 Screenshot saved: {screenshot_path}")
                except Exception as e:
                    logger.warning(f"Could not take screenshot: {e}")
            
            # Look for login/submit button
            button_selectors = [
                (By.CSS_SELECTOR, 'button[type="submit"]'),
                (By.XPATH, '//button[contains(text(), "Sign in")]'),
                (By.XPATH, '//button[contains(text(), "Log in")]'),
                (By.XPATH, '//button[contains(text(), "Login")]'),
                (By.CSS_SELECTOR, 'input[type="submit"]')
            ]
            
            login_button = None
            for by, selector in button_selectors:
                try:
                    login_button = self.wait.until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    if login_button:
                        logger.info(f"Found login button with selector: {selector}")
                        break
                except:
                    continue
                    
            if not login_button:
                logger.error("Could not find login button")
                return False
                
            # Click login button
            logger.info("🖱️  Clicking login button...")
            login_button.click()
            logger.info("✅ Login button clicked")
            
            if take_screenshots:
                try:
                    screenshot_path = str(SCREENSHOT_DIR / "prepworx_login_4_button_clicked.png")
                    self.driver.save_screenshot(screenshot_path)
                    logger.info(f"📸 Screenshot saved: {screenshot_path}")
                except Exception as e:
                    logger.warning(f"Could not take screenshot: {e}")
            
            # Wait for navigation after login (look for dashboard or profile elements)
            logger.info("⏳ Waiting for login to complete...")
            time.sleep(3)
            
            # Check if login was successful by looking for common post-login elements
            # This is a placeholder - you may need to adjust based on actual PrepWorx UI
            current_url = self.driver.current_url
            logger.info(f"📍 Current URL after login: {current_url}")
            
            if take_screenshots:
                try:
                    screenshot_path = str(SCREENSHOT_DIR / "prepworx_login_5_after_login.png")
                    self.driver.save_screenshot(screenshot_path)
                    logger.info(f"📸 Screenshot saved: {screenshot_path}")
                except Exception as e:
                    logger.warning(f"Could not take screenshot: {e}")
            
            # If we're not on the login page anymore, consider it successful
            if current_url != self.PREPWORX_URL or "dashboard" in current_url.lower() or "app" in current_url.lower():
                logger.info("✅ Login successful! Redirected to: " + current_url)
                return True
            else:
                logger.warning("⚠️  Login may have failed - still on login page")
                logger.warning(f"   Expected redirect, but URL is still: {current_url}")
                return False
                
        except TimeoutException as e:
            logger.error(f"Timeout during login: {e}")
            return False
        except Exception as e:
            logger.error(f"Error during login: {e}")
            return False
            
    def create_inbound(self, purchase_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create inbound entries for purchase records
        
        Args:
            purchase_records: List of purchase records to process
            
        Returns:
            Dictionary with results
        """
        if not self.driver:
            return {
                "success": False,
                "error": "Browser not started",
                "processed": 0,
                "total": len(purchase_records)
            }
            
        if not purchase_records:
            return {
                "success": True,
                "processed": 0,
                "total": 0,
                "message": "No records to process"
            }
            
        try:
            logger.info(f"Creating inbound for {len(purchase_records)} records...")
            
            # Step 1: Click "Create inbound" button/link after successful login
            logger.info("🔗 Navigating to Create Inbound page...")
            logger.info("   Looking for 'Create Inbound' button/link on the dashboard...")
            
            try:
                # Wait a moment for the dashboard to fully load after login
                time.sleep(2)
                
                # Try to find and click the "Create Inbound" link
                # The link has href="/shipments/inbound/create" and contains text "Create Inbound"
                create_inbound_selectors = [
                    (By.CSS_SELECTOR, 'a[href="/shipments/inbound/create"]'),  # Direct href match
                    (By.XPATH, '//a[contains(text(), "Create Inbound")]'),  # Text match
                    (By.XPATH, '//a[contains(text(), "CI")]'),  # The quick link button abbreviation
                ]
                
                create_inbound_link = None
                for by, selector in create_inbound_selectors:
                    try:
                        create_inbound_link = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((by, selector))
                        )
                        if create_inbound_link:
                            logger.info(f"   ✅ Found Create Inbound link with selector: {selector}")
                            break
                    except:
                        continue
                
                if create_inbound_link:
                    # Click the link
                    create_inbound_link.click()
                    logger.info("   ✅ Clicked 'Create Inbound' button/link")
                    # Wait for navigation
                    time.sleep(2)
                    logger.info("   ✅ Page navigated to Create Inbound form")
                else:
                    # Link not found, navigate directly to the URL
                    logger.info("   ⚠️  Link not found, navigating directly to URL...")
                    self.driver.get(f"{self.PREPWORX_URL}shipments/inbound/create")
                    time.sleep(2)
                    logger.info("   ✅ Navigated directly to Create Inbound form")
                
                # Verify we're on the correct page by checking for form elements
                logger.info("   ⏳ Verifying form page loaded...")
                form_indicators = [
                    (By.CSS_SELECTOR, 'form.n-form'),
                    (By.CSS_SELECTOR, 'input[placeholder*="Reference Name" i]'),
                    (By.XPATH, '//h3[contains(text(), "Shipment Information")]'),
                ]
                
                form_loaded = False
                for by, indicator in form_indicators:
                    try:
                        WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((by, indicator))
                        )
                        form_loaded = True
                        logger.info(f"   ✅ Form page verified (found: {indicator})")
                        break
                    except:
                        continue
                
                if not form_loaded:
                    logger.warning("   ⚠️  Could not verify form page loaded, but continuing...")
                
                # Additional wait to ensure form is fully rendered
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"   ❌ Error navigating to Create Inbound page: {e}")
                # Try direct navigation as fallback
                try:
                    logger.info("   🔄 Attempting direct navigation as fallback...")
                    self.driver.get(f"{self.PREPWORX_URL}shipments/inbound/create")
                    time.sleep(2)
                    logger.info("   ✅ Fallback navigation successful")
                except Exception as e2:
                    logger.error(f"   ❌ Fallback navigation also failed: {e2}")
                    return {
                        "success": False,
                        "error": f"Failed to navigate to Create Inbound page: {str(e2)}",
                        "processed": 0,
                        "total": len(purchase_records)
                    }
            
            # Process each purchase record
            processed_count = 0
            errors = []
            successful_record_ids = []  # Track successfully submitted record IDs
            
            for idx, record in enumerate(purchase_records, 1):
                try:
                    logger.info(f"\n📦 Processing record {idx}/{len(purchase_records)}: {record.get('order_number', 'N/A')}")
                    
                    # Get today's date in format YYYY-MM-DD
                    from datetime import date
                    today = date.today().strftime("%Y-%m-%d")
                    
                    # Extract data from record
                    order_number = record.get("order_number", "")
                    supplier = record.get("supplier", "")
                    product_name = record.get("product_name", "")
                    asin = record.get("asin", "")
                    sku_upc = record.get("sku_upc", "") or ""
                    ppu = record.get("ppu", 0) or 0
                    final_qty = record.get("final_qty", 0) or 0
                    
                    logger.info(f"   Order: {order_number}, Product: {product_name}, Qty: {final_qty}")
                    
                    # Step 2: Fill Shipment Information
                    logger.info("📝 Filling Shipment Information...")
                    
                    # Reference field - should be Order Number from purchase tracker record
                    reference_input = None
                    try:
                        # Find input in the "Shipment Information" section with label "Reference"
                        reference_selectors = [
                            (By.CSS_SELECTOR, 'input[placeholder*="Reference Name" i]'),
                            (By.CSS_SELECTOR, 'input[placeholder*="Reference" i]'),
                            (By.CSS_SELECTOR, 'input.n-input__input-el[type="text"]'),
                        ]
                        
                        reference_input = self._find_element_by_multiple_selectors(reference_selectors)
                        if reference_input:
                            logger.info(f"   Found Reference field")
                    except Exception as e:
                        logger.debug(f"   Debug: Error finding Reference field: {e}")
                    
                    if reference_input:
                        reference_input.clear()
                        reference_input.send_keys(order_number)
                        logger.info(f"   ✅ Filled Reference (Order Number): {order_number}")
                    else:
                        logger.warning("   ⚠️  Could not find Reference field")
                    
                    # Origin field
                    origin_input = None
                    try:
                        # Get all text inputs and find the one with origin placeholder
                        inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input.n-input__input-el[type="text"]')
                        for inp in inputs:
                            placeholder = inp.get_attribute('placeholder') or ''
                            if 'origin' in placeholder.lower():
                                origin_input = inp
                                break
                        
                        # If not found by placeholder, try second input (after Reference)
                        if not origin_input and len(inputs) > 1:
                            origin_input = inputs[1]
                    except Exception as e:
                        logger.debug(f"   Debug: Error finding Origin field: {e}")
                    
                    if origin_input:
                        origin_input.clear()
                        origin_input.send_keys(supplier)
                        logger.info(f"   ✅ Filled Origin: {supplier}")
                    else:
                        logger.warning("   ⚠️  Could not find Origin field")
                    
                    # Estimated Arrival Date - this is a date picker
                    logger.info("   📅 Filling Estimated Arrival Date...")
                    date_selectors = [
                        (By.CSS_SELECTOR, 'input[placeholder*="Select Date" i]'),
                        (By.CSS_SELECTOR, '.n-date-picker input'),
                        (By.CSS_SELECTOR, 'input.n-input__input-el[tabindex="-1"]'),
                    ]
                    
                    date_input = self._find_element_by_multiple_selectors(date_selectors)
                    
                    if date_input:
                        try:
                            # Click to open date picker
                            date_input.click()
                            time.sleep(0.5)
                            
                            # Try to find and click today's date in the calendar
                            today_button = None
                            try:
                                # Try to find today's date button
                                today_selectors = [
                                    (By.XPATH, '//button[contains(text(), "Today")]'),
                                    (By.CSS_SELECTOR, '.n-date-picker-calendar button[class*="today"]'),
                                    (By.XPATH, f'//div[contains(@class, "n-date-picker-calendar")]//button[text()="{date.today().day}"]'),
                                ]
                                
                                today_button = self._find_element_by_multiple_selectors(today_selectors, timeout=2)
                                
                                if today_button:
                                    today_button.click()
                                    logger.info(f"   ✅ Selected today's date from calendar")
                                else:
                                    # Fallback: try to fill the input directly
                                    date_input.clear()
                                    date_input.send_keys(today)
                                    logger.info(f"   ✅ Filled Estimated Arrival Date: {today}")
                            except:
                                # Fallback: fill input directly
                                date_input.clear()
                                date_input.send_keys(today)
                                logger.info(f"   ✅ Filled Estimated Arrival Date: {today}")
                        except Exception as e:
                            logger.warning(f"   ⚠️  Error setting date: {e}, trying direct fill...")
                            try:
                                date_input.clear()
                                date_input.send_keys(today)
                                logger.info(f"   ✅ Filled Estimated Arrival Date: {today}")
                            except:
                                logger.warning("   ⚠️  Could not set Estimated Arrival Date")
                    else:
                        logger.warning("   ⚠️  Could not find Estimated Arrival Date field")
                    
                    # Expected Packages - MUST be set to 1
                    logger.info("   📦 Filling Expected Packages (must be 1)...")
                    package_input = None
                    try:
                        # Find input in the Expected Packages section
                        # First, try to find by label text "Expected Packages"
                        all_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input.n-input__input-el[type="text"]')
                        
                        for inp in all_inputs:
                            # Skip the date input
                            if date_input and inp == date_input:
                                continue
                            
                            try:
                                # Check if this input is related to Expected Packages
                                # Look at the parent element's text content for "Expected Packages"
                                parent_text = self.driver.execute_script("""
                                    let parent = arguments[0].closest("div.col-span-6, div.col-span-3, div.n-form-item");
                                    if (!parent) parent = arguments[0].closest("div");
                                    let text = parent ? parent.textContent : '';
                                    
                                    // Also check for label elements
                                    let label = parent ? parent.querySelector('label, p, span') : null;
                                    if (label) text += ' ' + label.textContent;
                                    
                                    return text.toLowerCase();
                                """, inp)
                                
                                # Must contain "expected packages" and NOT contain "units" or "number"
                                if 'expected packages' in parent_text.lower():
                                    # Make sure it's not the "Number of Units" field
                                    if 'number of units' not in parent_text.lower() and 'units' not in parent_text.lower():
                                        package_input = inp
                                        logger.info(f"   Found Expected Packages field")
                                        break
                            except Exception as e:
                                logger.debug(f"   Debug: Error checking input: {e}")
                                continue
                        
                        # If not found, try more specific approach
                        if not package_input:
                            try:
                                # Look for input that comes after "Expected Packages" label
                                labels = self.driver.find_elements(By.XPATH, 
                                    '//label[contains(text(), "Expected Packages")] | //p[contains(text(), "Expected Packages")] | //span[contains(text(), "Expected Packages")]')
                                
                                for label in labels:
                                    try:
                                        # Find the input field near this label
                                        parent_container = self.driver.execute_script("""
                                            return arguments[0].closest("div.col-span-6, div.col-span-3, div.n-form-item");
                                        """, label)
                                        
                                        if parent_container:
                                            # Find input in the same container
                                            inputs_in_container = parent_container.find_elements(By.CSS_SELECTOR, 'input.n-input__input-el[type="text"]')
                                            if inputs_in_container:
                                                package_input = inputs_in_container[0]
                                                logger.info(f"   Found Expected Packages field via label")
                                                break
                                    except:
                                        continue
                            except Exception as e:
                                logger.debug(f"   Debug: Error finding via label: {e}")
                    except Exception as e:
                        logger.debug(f"   Debug: Error finding package input: {e}")
                    
                    if package_input:
                        # Clear the field completely and set to 1
                        try:
                            # Clear using multiple methods to ensure it's empty
                            package_input.clear()
                            # Also use JavaScript to clear
                            self.driver.execute_script("arguments[0].value = '';", package_input)
                            time.sleep(0.2)  # Small wait to ensure clear
                            
                            # Set to 1
                            package_input.send_keys("1")
                            
                            # Verify it's set to 1
                            current_value = package_input.get_attribute('value')
                            if current_value != "1":
                                # Force set using JavaScript
                                self.driver.execute_script("arguments[0].value = '1';", package_input)
                                # Trigger input event to ensure form recognizes the change
                                self.driver.execute_script("""
                                    arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                                """, package_input)
                            
                            final_value = package_input.get_attribute('value')
                            logger.info(f"   ✅ Filled Expected Packages: {final_value} (should be 1)")
                            
                            if final_value != "1":
                                logger.warning(f"   ⚠️  Expected Packages is {final_value}, not 1. Attempting to fix...")
                                # One more attempt
                                package_input.clear()
                                package_input.send_keys("1")
                        except Exception as e:
                            logger.warning(f"   ⚠️  Error setting Expected Packages: {e}")
                    else:
                        logger.warning("   ⚠️  Could not find Expected Packages field")
                    
                    # Shipment Notes (optional, leave empty)
                    # Skip for now as it's optional
                    
                    # Step 3: Fill Shipment Items
                    logger.info("📦 Filling Shipment Items...")
                    
                    # Name field (Item Name) - should be product_name from purchase tracker record
                    name_input = None
                    try:
                        # Find input in the "Shipment Items" section with label "Name"
                        # Get all inputs with Name placeholder
                        all_name_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input.n-input__input-el[placeholder*="Name" i]')
                        
                        for inp in all_name_inputs:
                            try:
                                # Check if this input is in the Shipment Items section
                                parent_text = self.driver.execute_script("""
                                    let parent = arguments[0].closest("div");
                                    for (let i = 0; i < 10; i++) {
                                        if (!parent) break;
                                        const text = parent.textContent || "";
                                        if (text.includes("Shipment Items") || text.includes("Item 1")) {
                                            return "items";
                                        }
                                        if (text.includes("Shipment Information") && !text.includes("Shipment Items")) {
                                            return "info";
                                        }
                                        parent = parent.parentElement;
                                    }
                                    return "";
                                """, inp)
                                
                                if parent_text == "items":
                                    name_input = inp
                                    logger.info("   Found Name field in Shipment Items section")
                                    break
                            except:
                                continue
                        
                        # Fallback: use last Name input (usually items section comes after info section)
                        if not name_input and all_name_inputs:
                            name_input = all_name_inputs[-1] if len(all_name_inputs) > 1 else all_name_inputs[0]
                    except Exception as e:
                        logger.debug(f"   Debug: Error finding Name field: {e}")
                    
                    if name_input:
                        name_input.clear()
                        name_input.send_keys(product_name)
                        logger.info(f"   ✅ Filled Name (Item Name / product_name): {product_name}")
                    else:
                        logger.warning("   ⚠️  Could not find Name field in Shipment Items section")
                    
                    # ASIN field
                    asin_input = None
                    try:
                        asin_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input.n-input__input-el[placeholder*="ASIN" i]')
                        if asin_inputs:
                            asin_input = asin_inputs[0]
                    except:
                        pass
                    
                    if asin_input:
                        asin_input.clear()
                        asin_input.send_keys(asin)
                        logger.info(f"   ✅ Filled ASIN: {asin}")
                    else:
                        logger.warning("   ⚠️  Could not find ASIN field")
                    
                    # UPC field (optional)
                    upc_input = None
                    try:
                        upc_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input.n-input__input-el[placeholder*="UPC" i]')
                        if upc_inputs:
                            upc_input = upc_inputs[0]
                    except:
                        pass
                    
                    if upc_input and sku_upc:
                        upc_input.clear()
                        upc_input.send_keys(sku_upc)
                        logger.info(f"   ✅ Filled UPC: {sku_upc}")
                    
                    # Unit Purchase Price - find input with $ prefix
                    price_input = None
                    try:
                        # Find all inputs and check their parent for $ prefix
                        all_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input.n-input__input-el')
                        for inp in all_inputs:
                            try:
                                # Use JavaScript to check if parent has $ prefix
                                has_dollar_prefix = self.driver.execute_script("""
                                    const parent = arguments[0].closest(".n-input");
                                    if (!parent) return false;
                                    const prefix = parent.querySelector(".n-input__prefix");
                                    return prefix && prefix.textContent.includes("$");
                                """, inp)
                                
                                if has_dollar_prefix:
                                    price_input = inp
                                    break
                            except:
                                continue
                    except Exception as e:
                        logger.debug(f"   Debug: Error finding price input: {e}")
                    
                    if price_input:
                        price_input.clear()
                        price_input.send_keys(str(ppu))
                        logger.info(f"   ✅ Filled Unit Purchase Price: ${ppu}")
                    else:
                        logger.warning("   ⚠️  Could not find Unit Purchase Price field")
                    
                    # Number of Units - set to final_qty
                    logger.info("   📊 Filling Number of Units...")
                    units_input = None
                    try:
                        # Find "Number of Units" input field
                        # Look for inputs that might be related to quantity/units
                        all_number_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input.n-input__input-el[type="text"]')
                        
                        for inp in all_number_inputs:
                            try:
                                # Check if this input is related to "Number of Units"
                                parent_text = self.driver.execute_script("""
                                    let parent = arguments[0].closest("div.col-span-6, div.col-span-3, div.n-form-item");
                                    if (!parent) parent = arguments[0].closest("div");
                                    return parent ? parent.textContent : '';
                                """, inp)
                                
                                if 'number of units' in parent_text.lower() or 'units' in parent_text.lower():
                                    # Make sure it's not the price field
                                    has_dollar = self.driver.execute_script("""
                                        const parent = arguments[0].closest(".n-input");
                                        if (!parent) return false;
                                        const prefix = parent.querySelector(".n-input__prefix");
                                        return prefix && prefix.textContent.includes("$");
                                    """, inp)
                                    
                                    if not has_dollar:
                                        units_input = inp
                                        break
                            except:
                                continue
                        
                        # Fallback: Try finding by placeholder or aria-label
                        if not units_input:
                            try:
                                units_input = self.driver.find_element(By.XPATH, 
                                    '//input[contains(@placeholder, "units") or contains(@aria-label, "units")]')
                            except:
                                pass
                    except Exception as e:
                        logger.debug(f"   Debug: Error finding Number of Units field: {e}")
                    
                    if units_input:
                        units_input.clear()
                        units_input.send_keys(str(final_qty))
                        logger.info(f"   ✅ Filled Number of Units: {final_qty}")
                    else:
                        logger.warning("   ⚠️  Could not find Number of Units field")
                    
                    # Notes/Instructions (optional, leave empty)
                    
                    # Step 4: Take screenshot of filled form before submitting
                    logger.info("📸 Taking screenshot of filled form...")
                    try:
                        screenshot_filename = f"prepworx_inbound_form_filled_{record.get('order_number', 'unknown')}_{idx}.png"
                        screenshot_path = str(SCREENSHOT_DIR / screenshot_filename)
                        self.driver.save_screenshot(screenshot_path)
                        logger.info(f"   ✅ Screenshot saved: {screenshot_path}")
                    except Exception as e:
                        logger.warning(f"   ⚠️  Could not take screenshot: {e}")
                    
                    # Step 5: Submit the form
                    logger.info("📤 Submitting form...")
                    
                    # Submit button selectors based on PrepWorx form HTML
                    submit_selectors = [
                        (By.CSS_SELECTOR, 'button.n-button--primary-type.n-button--ghost'),
                        (By.XPATH, '//button[contains(@class, "n-button--primary-type")]//span[contains(text(), "Submit")]/../..'),
                        (By.XPATH, '//button[contains(text(), "Submit")]'),
                        (By.CSS_SELECTOR, 'div.flex.justify-center button'),
                        (By.XPATH, '//span[@class="n-button__content" and contains(text(), "Submit")]/..'),
                    ]
                    
                    submit_button = None
                    for by, selector in submit_selectors:
                        try:
                            logger.info(f"   🔍 Trying selector: {selector}")
                            submit_button = WebDriverWait(self.driver, 3).until(
                                EC.element_to_be_clickable((by, selector))
                            )
                            if submit_button:
                                logger.info(f"   ✅ Found Submit button with selector: {selector}")
                                break
                        except:
                            continue
                    
                    # Fallback: find by JavaScript if selectors don't work
                    if not submit_button:
                        try:
                            logger.info("   🔍 Trying JavaScript fallback to find Submit button...")
                            submit_button = self.driver.execute_script("""
                                // Find button with "Submit" text
                                const buttons = document.querySelectorAll('button');
                                for (const btn of buttons) {
                                    if (btn.textContent.trim().toLowerCase() === 'submit') {
                                        return btn;
                                    }
                                }
                                // Find in n-button__content span
                                const spans = document.querySelectorAll('span.n-button__content');
                                for (const span of spans) {
                                    if (span.textContent.trim().toLowerCase() === 'submit') {
                                        return span.closest('button');
                                    }
                                }
                                return null;
                            """)
                            if submit_button:
                                logger.info("   ✅ Found Submit button via JavaScript")
                        except Exception as js_err:
                            logger.warning(f"   ⚠️  JavaScript fallback failed: {js_err}")
                    
                    if submit_button:
                        # Scroll the submit button into view first
                        try:
                            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", submit_button)
                            time.sleep(0.5)
                        except:
                            # If scroll fails, try scrolling to bottom
                            self.driver.execute_script('window.scrollTo(0, document.body.scrollHeight)')
                            time.sleep(0.5)
                        
                        # Take a screenshot before clicking submit
                        try:
                            pre_submit_screenshot = str(SCREENSHOT_DIR / f"prepworx_pre_submit_{record.get('order_number', 'unknown')}_{idx}.png")
                            self.driver.save_screenshot(pre_submit_screenshot)
                            logger.info(f"   📸 Pre-submit screenshot: {pre_submit_screenshot}")
                        except:
                            pass
                        
                        # Click submit button using JavaScript for more reliable click
                        try:
                            self.driver.execute_script("arguments[0].click();", submit_button)
                            logger.info("   ✅ Clicked Submit button (via JavaScript)")
                        except:
                            # Fallback to regular click
                            submit_button.click()
                            logger.info("   ✅ Clicked Submit button")
                        
                        # Wait for submission to complete
                        logger.info("   ⏳ Waiting for submission to complete...")
                        
                        # Check for success/error messages on the page
                        submission_success = False
                        submission_error = None
                        
                        try:
                            # Give time for submission and any notifications to appear
                            time.sleep(2)
                            
                            current_url = self.driver.current_url
                            logger.info(f"   📍 Current URL after submit: {current_url}")
                            
                            # Check if we're redirected away from create page (usually means success)
                            if '/shipments/inbound/create' not in current_url:
                                submission_success = True
                                logger.info("   ✅ Submission appears successful (redirected from create page)")
                            else:
                                # Check for Naive UI toast notifications (commonly used for success/error)
                                toast_selectors = [
                                    (By.CSS_SELECTOR, '.n-message'),
                                    (By.CSS_SELECTOR, '.n-notification'),
                                    (By.CSS_SELECTOR, '[class*="n-message"]'),
                                    (By.CSS_SELECTOR, '[class*="notification"]'),
                                    (By.CSS_SELECTOR, '[role="alert"]'),
                                    (By.CSS_SELECTOR, '.toast'),
                                ]
                                
                                toast_found = False
                                toast_text = ""
                                for by, selector in toast_selectors:
                                    try:
                                        toast_elements = self.driver.find_elements(by, selector)
                                        for toast in toast_elements:
                                            if toast.is_displayed():
                                                toast_text = toast.text.lower()
                                                toast_found = True
                                                logger.info(f"   📢 Found notification: {toast_text[:100]}...")
                                                break
                                    except:
                                        continue
                                    if toast_found:
                                        break
                                
                                if toast_found:
                                    if any(word in toast_text for word in ['success', 'created', 'submitted', 'saved']):
                                        submission_success = True
                                        logger.info("   ✅ Submission successful (success notification found)")
                                    elif any(word in toast_text for word in ['error', 'fail', 'invalid', 'required']):
                                        submission_error = f"Error notification: {toast_text[:200]}"
                                        logger.error(f"   ❌ {submission_error}")
                                
                                # If no toast found, check for inline validation errors
                                if not toast_found and not submission_success:
                                    logger.info("   🔍 Checking for validation errors...")
                                    
                                    # Look for validation error messages in form
                                    validation_error_selectors = [
                                        (By.CSS_SELECTOR, '.n-form-item-feedback-wrapper'),
                                        (By.CSS_SELECTOR, '[class*="error-message"]'),
                                        (By.CSS_SELECTOR, '[class*="validation-error"]'),
                                        (By.CSS_SELECTOR, '.n-form-item--error'),
                                        (By.CSS_SELECTOR, 'span.text-red-700'),
                                        (By.CSS_SELECTOR, '[class*="invalid"]'),
                                    ]
                                    
                                    validation_errors = []
                                    for by, selector in validation_error_selectors:
                                        try:
                                            error_elements = self.driver.find_elements(by, selector)
                                            for err in error_elements:
                                                if err.is_displayed():
                                                    err_text = err.text.strip()
                                                    if err_text and err_text != '*':
                                                        validation_errors.append(err_text)
                                        except:
                                            continue
                                    
                                    if validation_errors:
                                        submission_error = f"Validation errors: {'; '.join(validation_errors[:5])}"
                                        logger.error(f"   ❌ {submission_error}")
                                    else:
                                        # No clear error found, check page content
                                        try:
                                            page_text = self.driver.find_element(By.TAG_NAME, 'body').text.lower()
                                        except:
                                            page_text = ""
                                        
                                        # Check for success keywords in page
                                        if any(indicator in page_text for indicator in ['successfully created', 'inbound created', 'shipment created']):
                                            submission_success = True
                                            logger.info("   ✅ Submission appears successful (success text in page)")
                                        else:
                                            # Check if the form has been reset (fields are empty) - indicates success
                                            try:
                                                ref_field = self.driver.find_element(By.CSS_SELECTOR, 'input[placeholder*="Reference Name" i]')
                                                if ref_field:
                                                    ref_value = ref_field.get_attribute('value')
                                                    if not ref_value:
                                                        submission_success = True
                                                        logger.info("   ✅ Form was reset (fields empty) - submission likely successful")
                                                    else:
                                                        logger.warning(f"   ⚠️  Reference field still has value: {ref_value}")
                                            except:
                                                pass
                                            
                                            # Final check: wait a bit more and see if URL changes
                                            if not submission_success:
                                                logger.info("   ⏳ Waiting a bit more for any changes...")
                                                time.sleep(3)
                                                new_url = self.driver.current_url
                                                if '/shipments/inbound/create' not in new_url:
                                                    submission_success = True
                                                    logger.info(f"   ✅ Submission successful (redirected to: {new_url})")
                                                else:
                                                    # Last resort: assume failure if still on same page with form
                                                    try:
                                                        form_visible = self.driver.find_element(By.CSS_SELECTOR, 'form.n-form')
                                                        if form_visible.is_displayed():
                                                            submission_error = "Form still visible after submit - submission may have failed. Check screenshot for details."
                                                            logger.error(f"   ❌ {submission_error}")
                                                        else:
                                                            submission_success = True
                                                            logger.info("   ✅ Form no longer visible - submission likely successful")
                                                    except:
                                                        submission_success = True
                                                        logger.info("   ✅ Form no longer visible - submission likely successful")
                                        
                        except Exception as e:
                            logger.warning(f"   ⚠️  Error checking submission status: {e}")
                            # If we can't determine, check URL
                            current_url = self.driver.current_url
                            if '/shipments/inbound/create' not in current_url:
                                submission_success = True
                        
                        # Take screenshot after submission
                        logger.info("📸 Taking screenshot after submission...")
                        try:
                            screenshot_filename = f"prepworx_inbound_submitted_{record.get('order_number', 'unknown')}_{idx}.png"
                            screenshot_path = str(SCREENSHOT_DIR / screenshot_filename)
                            self.driver.save_screenshot(screenshot_path)
                            logger.info(f"   ✅ Screenshot saved: {screenshot_path}")
                        except Exception as e:
                            logger.warning(f"   ⚠️  Could not take screenshot: {e}")
                        
                        # Mark record for database update if successful
                        if submission_success:
                            processed_count += 1
                            # Store record ID for database update
                            record_id = record.get("id")
                            if record_id:
                                successful_record_ids.append(record_id)
                            logger.info(f"   ✅ Successfully submitted record {idx} (ID: {record_id})")
                        else:
                            error_msg = submission_error or "Submission failed - could not verify success"
                            logger.error(f"   ❌ {error_msg}")
                            errors.append(f"Record {idx} (ID: {record.get('id')}): {error_msg}")
                    else:
                        error_msg = "Could not find Submit button"
                        logger.error(f"   ❌ {error_msg}")
                        errors.append(f"Record {idx} (ID: {record.get('id')}): {error_msg}")
                    
                    # If there are more records, we need to navigate back to create another inbound
                    if idx < len(purchase_records):
                        logger.info("   🔄 Navigating to create next inbound...")
                        time.sleep(1)
                        self.driver.get(f"{self.PREPWORX_URL}shipments/inbound/create")
                        time.sleep(2)
                    
                except Exception as e:
                    error_msg = f"Error processing record {idx}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    errors.append(error_msg)
            
            logger.info(f"\n✅ Inbound creation completed: {processed_count}/{len(purchase_records)} processed")
            logger.info(f"   Successfully submitted record IDs: {successful_record_ids}")
            
            return {
                "success": processed_count > 0,
                "processed": processed_count,
                "total": len(purchase_records),
                "successful_record_ids": successful_record_ids,  # IDs to update in database
                "errors": errors if errors else None
            }
            
        except Exception as e:
            logger.error(f"Error creating inbound: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "processed": 0,
                "total": len(purchase_records)
            }
    
    def navigate_to_inventory(self, take_screenshots: bool = False) -> Dict[str, Any]:
        """
        Navigate to inventory page, click "View Inventory", and download CSV
        
        Args:
            take_screenshots: Whether to take screenshots during navigation
            
        Returns:
            Dictionary with results including screenshot path and CSV file path
        """
        if not self.driver:
            return {
                "success": False,
                "error": "Browser not started",
                "screenshot_path": None
            }
        
        try:
            logger.info("🔗 Navigating to dashboard to find 'View Inventory' link...")
            
            # Navigate to the main dashboard/app page first (where the View Inventory link is)
            # After login, we should be on the dashboard
            logger.info(f"   📍 Current URL: {self.driver.current_url}")
            
            # Wait for page to fully load
            time.sleep(2)
            
            if take_screenshots:
                try:
                    screenshot_path = str(SCREENSHOT_DIR / "prepworx_dashboard_before_inventory.png")
                    self.driver.save_screenshot(screenshot_path)
                    logger.info(f"📸 Screenshot saved: {screenshot_path}")
                except Exception as e:
                    logger.warning(f"Could not take screenshot: {e}")
            
            # Look for "View Inventory" link/button
            # Based on the HTML provided: <a href="/inventory" class=""> with text "View Inventory"
            logger.info("   🔍 Looking for 'View Inventory' link...")
            
            view_inventory_selectors = [
                (By.CSS_SELECTOR, 'a[href="/inventory"]'),
                (By.XPATH, '//a[contains(text(), "View Inventory")]'),
                (By.XPATH, '//a[contains(text(), "VI")]'),  # The quick link button abbreviation
                (By.XPATH, '//li[contains(@class, "col-span-1")]//a[contains(@href, "/inventory")]'),
                (By.XPATH, '//ul[@role="list"]//a[contains(@href, "/inventory")]'),
            ]
            
            view_inventory_link = None
            for by, selector in view_inventory_selectors:
                try:
                    view_inventory_link = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    if view_inventory_link:
                        logger.info(f"   ✅ Found View Inventory link with selector: {selector}")
                        break
                except:
                    continue
            
            if view_inventory_link:
                # Click the link
                logger.info("   🖱️  Clicking 'View Inventory' link...")
                view_inventory_link.click()
                logger.info("   ✅ Clicked 'View Inventory' link")
                
                # Wait for navigation/load
                time.sleep(3)
                
                # Take screenshot after clicking
                logger.info("📸 Taking screenshot of inventory page...")
                try:
                    screenshot_filename = "prepworx_inventory_view.png"
                    screenshot_path = str(SCREENSHOT_DIR / screenshot_filename)
                    self.driver.save_screenshot(screenshot_path)
                    logger.info(f"   ✅ Screenshot saved: {screenshot_path}")
                except Exception as e:
                    logger.warning(f"   ⚠️  Could not take screenshot: {e}")
                
                # Click "Download as CSV" button
                logger.info("📥 Looking for 'Download as CSV' button...")
                csv_file_path = None
                try:
                    # Look for download button - based on HTML, it's a button with download icon
                    # The download button has an SVG with path containing "M336 176" and "M176 272"
                    download_selectors = [
                        (By.XPATH, '//button[contains(@class, "n-button--success-type")]//svg//path[contains(@d, "M336 176")]'),  # Download icon SVG path
                        (By.XPATH, '//button[contains(@class, "n-button")]//svg//path[contains(@d, "M176 272")]'),  # Download arrow path
                        (By.XPATH, '//button[.//svg//path[contains(@d, "M336 176")]]'),  # Button containing download icon
                        (By.XPATH, '//button[contains(@class, "n-button")][.//i[contains(@class, "n-icon")]//svg//path[contains(@d, "M336 176")]]'),  # Button with icon containing download SVG
                        (By.XPATH, '//button[contains(@aria-label, "Download") or contains(@aria-label, "CSV")]'),
                        (By.XPATH, '//button[contains(@class, "n-button--success-type")][not(.//div[contains(@class, "n-checkbox")])]'),  # Success button that's not the checkbox button
                    ]
                    
                    download_button = None
                    for by, selector in download_selectors:
                        try:
                            download_button = WebDriverWait(self.driver, 10).until(
                                EC.element_to_be_clickable((by, selector))
                            )
                            if download_button:
                                logger.info(f"   ✅ Found Download button with selector: {selector}")
                                break
                        except:
                            continue
                    
                    # Fallback: Find button by checking SVG content
                    if not download_button:
                        try:
                            logger.info("   🔍 Trying fallback method: checking all buttons for download icon...")
                            all_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'button.n-button--success-type')
                            for btn in all_buttons:
                                try:
                                    # Check if button contains download icon SVG
                                    svg_paths = btn.find_elements(By.XPATH, './/svg//path[contains(@d, "M336 176")]')
                                    if svg_paths:
                                        # Make sure it's not the checkbox button
                                        checkbox = btn.find_elements(By.CSS_SELECTOR, '.n-checkbox')
                                        if not checkbox:
                                            download_button = btn
                                            logger.info("   ✅ Found Download button via fallback method")
                                            break
                                except:
                                    continue
                        except Exception as e:
                            logger.debug(f"   Fallback method failed: {e}")
                    
                    if download_button:
                        # Get list of files before download
                        files_before = set(SCREENSHOT_DIR.glob("*.csv"))
                        
                        # Click download button
                        logger.info("   🖱️  Clicking 'Download as CSV' button...")
                        download_button.click()
                        logger.info("   ✅ Clicked Download button")
                        
                        # Wait for download to complete (check for new CSV file)
                        logger.info("   ⏳ Waiting for CSV download to complete...")
                        max_wait = 30  # Maximum wait time in seconds
                        wait_interval = 1  # Check every second
                        downloaded = False
                        
                        for i in range(max_wait):
                            time.sleep(wait_interval)
                            files_after = set(SCREENSHOT_DIR.glob("*.csv"))
                            new_files = files_after - files_before
                            
                            if new_files:
                                # Found new CSV file
                                csv_file = new_files.pop()
                                # Wait a bit more to ensure download is complete (no .crdownload extension)
                                time.sleep(2)
                                
                                # Check if file still exists and is not a temp download file
                                if csv_file.exists() and not csv_file.name.endswith('.crdownload'):
                                    csv_file_path = str(csv_file)
                                    logger.info(f"   ✅ CSV file downloaded: {csv_file_path}")
                                    downloaded = True
                                    break
                        
                        if not downloaded:
                            logger.warning("   ⚠️  CSV download may not have completed or file not found")
                    else:
                        logger.warning("   ⚠️  Could not find Download as CSV button")
                        
                except Exception as e:
                    logger.warning(f"   ⚠️  Error downloading CSV: {e}")
                
                return {
                    "success": True,
                    "screenshot_path": screenshot_path if 'screenshot_path' in locals() else None,
                    "csv_file_path": csv_file_path,
                    "url": self.driver.current_url
                }
            else:
                # If link not found, try navigating directly to inventory page
                logger.info("   ⚠️  View Inventory link not found, navigating directly to /inventory...")
                try:
                    inventory_url = f"{self.PREPWORX_URL}inventory"
                    self.driver.get(inventory_url)
                    time.sleep(3)
                    
                    # Take screenshot
                    screenshot_filename = "prepworx_inventory_view.png"
                    screenshot_path = str(SCREENSHOT_DIR / screenshot_filename)
                    self.driver.save_screenshot(screenshot_path)
                    logger.info(f"   ✅ Screenshot saved: {screenshot_path}")
                    
                    # Click "Download as CSV" button
                    logger.info("📥 Looking for 'Download as CSV' button...")
                    csv_file_path = None
                    try:
                        # Look for download button
                        download_selectors = [
                            (By.XPATH, '//button[contains(@class, "n-button--success-type")]//svg//path[contains(@d, "M336 176")]'),  # Download icon SVG path
                            (By.XPATH, '//button[contains(@class, "n-button")]//svg//path[contains(@d, "M176 272")]'),  # Download arrow path
                            (By.XPATH, '//button[.//svg//path[contains(@d, "M336 176")]]'),  # Button containing download icon
                            (By.XPATH, '//button[contains(@class, "n-button")][.//i[contains(@class, "n-icon")]//svg//path[contains(@d, "M336 176")]]'),  # Button with icon containing download SVG
                            (By.XPATH, '//button[contains(@aria-label, "Download") or contains(@aria-label, "CSV")]'),
                            (By.XPATH, '//button[contains(@class, "n-button--success-type")][not(.//div[contains(@class, "n-checkbox")])]'),  # Success button that's not the checkbox button
                        ]
                        
                        download_button = None
                        for by, selector in download_selectors:
                            try:
                                download_button = WebDriverWait(self.driver, 10).until(
                                    EC.element_to_be_clickable((by, selector))
                                )
                                if download_button:
                                    logger.info(f"   ✅ Found Download button with selector: {selector}")
                                    break
                            except:
                                continue
                        
                        # Fallback: Find button by checking SVG content
                        if not download_button:
                            try:
                                logger.info("   🔍 Trying fallback method: checking all buttons for download icon...")
                                all_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'button.n-button--success-type')
                                for btn in all_buttons:
                                    try:
                                        # Check if button contains download icon SVG
                                        svg_paths = btn.find_elements(By.XPATH, './/svg//path[contains(@d, "M336 176")]')
                                        if svg_paths:
                                            # Make sure it's not the checkbox button
                                            checkbox = btn.find_elements(By.CSS_SELECTOR, '.n-checkbox')
                                            if not checkbox:
                                                download_button = btn
                                                logger.info("   ✅ Found Download button via fallback method")
                                                break
                                    except:
                                        continue
                            except Exception as e:
                                logger.debug(f"   Fallback method failed: {e}")
                        
                        if download_button:
                            # Get list of files before download
                            files_before = set(SCREENSHOT_DIR.glob("*.csv"))
                            
                            # Click download button
                            logger.info("   🖱️  Clicking 'Download as CSV' button...")
                            download_button.click()
                            logger.info("   ✅ Clicked Download button")
                            
                            # Wait for download to complete
                            logger.info("   ⏳ Waiting for CSV download to complete...")
                            max_wait = 30
                            wait_interval = 1
                            downloaded = False
                            
                            for i in range(max_wait):
                                time.sleep(wait_interval)
                                files_after = set(SCREENSHOT_DIR.glob("*.csv"))
                                new_files = files_after - files_before
                                
                                if new_files:
                                    csv_file = new_files.pop()
                                    time.sleep(2)
                                    
                                    if csv_file.exists() and not csv_file.name.endswith('.crdownload'):
                                        csv_file_path = str(csv_file)
                                        logger.info(f"   ✅ CSV file downloaded: {csv_file_path}")
                                        downloaded = True
                                        break
                            
                            if not downloaded:
                                logger.warning("   ⚠️  CSV download may not have completed or file not found")
                        else:
                            logger.warning("   ⚠️  Could not find Download as CSV button")
                            
                    except Exception as e:
                        logger.warning(f"   ⚠️  Error downloading CSV: {e}")
                    
                    return {
                        "success": True,
                        "screenshot_path": screenshot_path,
                        "csv_file_path": csv_file_path,
                        "url": self.driver.current_url,
                        "note": "View Inventory link not found, navigated directly to /inventory"
                    }
                except Exception as e:
                    logger.warning(f"   ⚠️  Could not navigate or take screenshot: {e}")
                    return {
                        "success": False,
                        "error": f"Could not find View Inventory link and direct navigation failed: {str(e)}",
                        "screenshot_path": None,
                        "csv_file_path": None
                    }
                    
        except Exception as e:
            logger.error(f"Error navigating to inventory: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "screenshot_path": None,
                "csv_file_path": None
            }
def process_inbound_creation(purchase_records: List[Dict[str, Any]], 
                             headless: bool = True) -> Dict[str, Any]:
    """
    Main function to process inbound creation for purchase records
    
    Args:
        purchase_records: List of purchase records grouped by address
        headless: Whether to run browser in headless mode
        
    Returns:
        Dictionary with processing results
    """
    results = {
        "success": False,
        "total_records": len(purchase_records),
        "processed_by_address": {},
        "successful_record_ids": [],  # All successfully submitted record IDs
        "errors": []
    }
    
    # Check Selenium availability first
    if not SELENIUM_AVAILABLE:
        error_msg = "Selenium not installed. Please install: pip install selenium"
        logger.error(error_msg)
        results["errors"].append(error_msg)
        return results
    
    if not purchase_records:
        results["success"] = True
        results["message"] = "No records to process"
        return results
        
    # Group records by address
    records_by_address = {}
    for record in purchase_records:
        address = record.get("address", "")
        if address not in records_by_address:
            records_by_address[address] = []
        records_by_address[address].append(record)
        
    logger.info(f"Processing {len(purchase_records)} records across {len(records_by_address)} addresses")
    
    # Process each address group
    for address, records in records_by_address.items():
        logger.info(f"\nProcessing {len(records)} records for address: {address}")
        
        # Get credentials for this address
        credentials = PrepWorxCredentials.get_credentials_by_address(address)
        
        if not credentials:
            error_msg = f"No credentials found for address: {address}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            results["processed_by_address"][address] = {
                "success": False,
                "error": error_msg,
                "count": len(records)
            }
            continue
            
        # Start automation
        with PrepWorxAutomation() as automation:
            # Start browser
            if not automation.start_browser(headless=headless):
                error_msg = f"Failed to start browser for address: {address}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                results["processed_by_address"][address] = {
                    "success": False,
                    "error": error_msg,
                    "count": len(records)
                }
                continue
                
            # Login with screenshots enabled for debugging
            # Screenshots will be saved to backend/tmp/prepworx_login_*.png
            take_screenshots = not headless  # Take screenshots if not headless, or always for debugging
            if not automation.login(credentials["email"], credentials["password"], take_screenshots=True):
                error_msg = f"Failed to login for address: {address}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                results["processed_by_address"][address] = {
                    "success": False,
                    "error": error_msg,
                    "count": len(records)
                }
                continue
                
            # Create inbound
            inbound_result = automation.create_inbound(records)
            results["processed_by_address"][address] = {
                "success": inbound_result["success"],
                "processed": inbound_result["processed"],
                "total": inbound_result["total"],
                "count": len(records)
            }
            
            # Collect successful record IDs for database update
            if inbound_result.get("successful_record_ids"):
                results["successful_record_ids"].extend(inbound_result["successful_record_ids"])
            
            # Collect errors
            if inbound_result.get("errors"):
                if isinstance(inbound_result["errors"], list):
                    results["errors"].extend(inbound_result["errors"])
                else:
                    results["errors"].append(inbound_result["errors"])
            elif inbound_result.get("error"):
                results["errors"].append(inbound_result["error"])
                
    # Overall success if no errors
    results["success"] = len(results["errors"]) == 0
    
    return results


