"""
Operation: Smart-Scrape
Mission: Extract all mobile phone data from smartprix.com
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import pandas as pd
import time

# Configuration
TARGET_URL = "https://www.smartprix.com/mobiles"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"

def setup_driver():
    """Initialize Chrome driver with proper configuration"""
    options = webdriver.ChromeOptions()
    options.add_argument(f'user-agent={USER_AGENT}')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Use Selenium Manager (built-in) to auto-download correct ChromeDriver
    driver = webdriver.Chrome(options=options)
    return driver

def extract_mobile_data(soup):
    """Extract data from all mobile containers on the page"""
    mobiles_data = []
    
    containers = soup.find_all('div', class_='sm-product')
    print(f"Found {len(containers)} mobile containers on this page")
    
    for container in containers:
        try:
            # Extract Name
            name_elem = container.find('h2')
            name = name_elem.get_text(strip=True) if name_elem else "N/A"
            
            # Extract Price - try multiple selectors
            price = "N/A"
            price_elem = container.find('span', class_='sm-p-price')
            if not price_elem:
                price_elem = container.find('span', class_='price')
            if not price_elem:
                price_elem = container.find('div', class_='sm-price')
            if price_elem:
                price = price_elem.get_text(strip=True)
            
            # Extract Image URL
            img_elem = container.find('img', class_='sm-product-img')
            image_url = img_elem.get('src') if img_elem else "N/A"
            
            # Extract Specs (list of features)
            specs_list = []
            specs_ul = container.find('ul', class_='sm-feat')
            if specs_ul:
                specs_items = specs_ul.find_all('li')
                specs_list = [li.get_text(strip=True) for li in specs_items]
            specs = " | ".join(specs_list) if specs_list else "N/A"
            
            mobiles_data.append({
                'Name': name,
                'Price': price,
                'Image_URL': image_url,
                'Specs': specs
            })
            
        except Exception as e:
            print(f"Error extracting data from a container: {e}")
            continue
    
    return mobiles_data

def click_next_page(driver, wait):
    """Click the next/load more button if available"""
    try:
        # First try to find "Load More" button (div with class sm-load-more)
        try:
            load_more = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.sm-load-more"))
            )
            
            # Check if it has disabled class or style
            if 'disabled' in load_more.get_attribute('class'):
                print("Load more button is disabled. Reached last page.")
                return False
            
            # Scroll to button and click
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more)
            time.sleep(1)
            load_more.click()
            print("Clicked 'Load More' button")
            
            # Wait for new content to load
            time.sleep(3)
            return True
            
        except TimeoutException:
            # Try alternative selector: a.sm-b-next
            next_button = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.sm-b-next"))
            )
            
            # Check if the button is disabled
            if 'disabled' in next_button.get_attribute('class'):
                print("Next button is disabled. Reached last page.")
                return False
            
            # Wait for it to be clickable
            next_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.sm-b-next"))
            )
            
            # Scroll to button and click
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
            time.sleep(1)
            next_button.click()
            print("Clicked 'Next' button")
            
            # Wait for page to load
            time.sleep(3)
            
            return True
        
    except TimeoutException:
        print("No pagination button found. Reached last page.")
        return False
    except Exception as e:
        print(f"Error clicking pagination button: {e}")
        return False

def main():
    """Main scraping operation"""
    print("=" * 60)
    print("OPERATION: SMART-SCRAPE INITIATED")
    print("=" * 60)
    
    driver = None
    all_mobiles = []
    seen_names = set()  # Track seen mobiles to avoid duplicates
    page_count = 0
    
    try:
        # Setup driver
        print("\n[*] Setting up Chrome driver...")
        driver = setup_driver()
        wait = WebDriverWait(driver, 10)
        
        # Navigate to target
        print(f"[*] Navigating to target: {TARGET_URL}")
        driver.get(TARGET_URL)
        time.sleep(3)  # Initial page load
        
        # Scraping loop
        while True:
            page_count += 1
            print(f"\n[*] Scraping page {page_count}...")
            
            # Get page source and parse with BeautifulSoup
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract mobile data
            mobiles = extract_mobile_data(soup)
            
            # Filter out duplicates
            new_mobiles = []
            for mobile in mobiles:
                # Create unique identifier from name and specs
                unique_id = f"{mobile['Name']}|{mobile['Specs']}"
                if unique_id not in seen_names:
                    seen_names.add(unique_id)
                    new_mobiles.append(mobile)
            
            all_mobiles.extend(new_mobiles)
            print(f"[+] Extracted {len(mobiles)} mobiles from page {page_count}")
            print(f"[+] New unique mobiles: {len(new_mobiles)}")
            print(f"[+] Total unique mobiles collected: {len(all_mobiles)}")
            
            # If no new mobiles found, we've reached the end
            if len(new_mobiles) == 0:
                print("\n[*] No new mobiles found. All data collected.")
                break
            
            # Try to navigate to next page
            if not click_next_page(driver, wait):
                print("\n[*] No more pages to scrape. Operation complete.")
                break
        
        # Save to CSV
        if all_mobiles:
            print(f"\n[*] Saving data to mobile.csv...")
            df = pd.DataFrame(all_mobiles)
            df.to_csv('mobile.csv', index=False, encoding='utf-8-sig')
            print(f"[+] Successfully saved {len(all_mobiles)} unique mobiles to mobile.csv")
            print(f"\n[+] Data columns: {list(df.columns)}")
            print(f"[+] First few entries:")
            print(df.head(3).to_string())
        else:
            print("\n[-] No data was collected.")
        
    except Exception as e:
        print(f"\n[!] CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if driver:
            print("\n[*] Closing browser...")
            driver.quit()
        
        print("\n" + "=" * 60)
        print("OPERATION: SMART-SCRAPE TERMINATED")
        print("=" * 60)

if __name__ == "__main__":
    main()
