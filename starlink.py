from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import csv
import time
import re
from datetime import datetime
import json

# Setup Chrome
options = Options()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--disable-extensions")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
options.add_argument("--start-maximized")

# Create driver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

# Your Starlink URL
url = "https://starlink.com/account/service-line/AST-2293597-46342-54?selectedDevice=ut01000000-00000000-0060d786&page=0&limit=5"
driver.get(url)

print("=== Starlink Data Usage Scraper ===")
print("1. Please log in when the browser window opens")
print("2. Wait for the dashboard to fully load")
print("3. Press Enter here once you're logged in and can see your data usage")
print()
input("Press Enter to continue after login...")

# Wait for the page to load completely
try:
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    time.sleep(5)
except Exception as e:
    print(f"Warning: Page load timeout - {e}")

# Dictionary to store all extracted data
starlink_data = {}

print("\n📊 Extracting Starlink Residential Data...")

# METHOD 1: Extract Total Data Usage
try:
    # Look for the main total data usage number
    total_usage_selectors = [
        "//*[contains(text(), 'Total Data Usage')]/following-sibling::*",
        "//div[contains(text(), 'Total Data Usage')]/following-sibling::div",
        "//h2[contains(text(), 'Total Data Usage')]/following-sibling::*",
        "[class*='total-usage']",
        "[class*='totalUsage']"
    ]
    
    for selector in total_usage_selectors:
        if selector.startswith("//"):  # XPath
            elements = driver.find_elements(By.XPATH, selector)
        else:  # CSS Selector
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        
        for elem in elements:
            text = elem.text.strip()
            # Look for numbers followed by GB
            match = re.search(r'(\d+(?:,\d+)?)\s*GB', text)
            if match:
                starlink_data['total_usage_gb'] = match.group(1).replace(',', '')
                print(f"✓ Total Data Usage: {starlink_data['total_usage_gb']} GB")
                break
        if 'total_usage_gb' in starlink_data:
            break
    
    # If not found, search entire page text
    if 'total_usage_gb' not in starlink_data:
        page_text = driver.find_element(By.TAG_NAME, "body").text
        match = re.search(r'Total Data Usage\s*\n\s*(\d+(?:,\d+)?)\s*GB', page_text)
        if match:
            starlink_data['total_usage_gb'] = match.group(1).replace(',', '')
            print(f"✓ Total Data Usage: {starlink_data['total_usage_gb']} GB")
            
except Exception as e:
    print(f"Could not extract total usage: {e}")

# METHOD 2: Extract Plan Information
try:
    # Look for Residential Data information
    plan_selectors = [
        "//*[contains(text(), 'Residential Data')]",
        "[class*='plan-info']",
        "[class*='subscription']"
    ]
    
    for selector in plan_selectors:
        if selector.startswith("//"):  # XPath
            elements = driver.find_elements(By.XPATH, selector)
        else:  # CSS Selector
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        
        for elem in elements:
            text = elem.text.strip()
            if 'Residential Data' in text:
                starlink_data['plan_type'] = 'Residential'
                # Extract included data
                match = re.search(r'(\d+(?:,\d+)?)\s*GB\s*Included', text)
                if match:
                    starlink_data['included_data_gb'] = match.group(1).replace(',', '')
                print(f"✓ Plan: {starlink_data.get('plan_type', 'Residential')}")
                if 'included_data_gb' in starlink_data:
                    print(f"✓ Included Data: {starlink_data['included_data_gb']} GB")
                break
        if 'plan_type' in starlink_data:
            break
            
except Exception as e:
    print(f"Could not extract plan info: {e}")

# METHOD 3: Extract Monthly/Period Data Usage (from bar chart)
try:
    monthly_data = []
    
    # Look for the bar chart data
    # Common patterns for chart data
    chart_selectors = [
        "[class*='bar']",
        "[class*='chart']",
        "[role='graphics-symbol']",
        ".recharts-bar-rectangle",  # If using Recharts library
        "[class*='data-point']"
    ]
    
    # Also look for month labels and values
    page_text = driver.find_element(By.TAG_NAME, "body").text
    
    # Find the months section
    months_section = re.search(r'(Nov|Dec|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct).*?(?:GB|MB)', page_text, re.DOTALL)
    
    if months_section:
        # Extract months and their values
        months = re.findall(r'(Nov|Dec|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct)', page_text)
        
        # Look for GB values near the months
        gb_values = re.findall(r'(\d+(?:\.\d+)?)\s*GB', page_text)
        
        # Match months with values (excluding the total)
        if len(months) > 0 and len(gb_values) > 1:
            for i, month in enumerate(months):
                if i < len(gb_values) - 1:  # Exclude the total (usually last or first)
                    monthly_data.append({
                        'period': month,
                        'usage_gb': gb_values[i]
                    })
    
    # Alternative: Look for specific chart data in JavaScript
    chart_data = driver.execute_script("""
        // Try to find chart data in common locations
        let data = null;
        
        // Check for React props
        if (window.__REACT_DEVTOOLS_GLOBAL_HOOK__) {
            // This might contain component data
        }
        
        // Look for data in DOM attributes
        const chartElements = document.querySelectorAll('[data-usage], [data-value]');
        if (chartElements.length > 0) {
            data = Array.from(chartElements).map(el => ({
                period: el.getAttribute('data-period') || el.getAttribute('data-label'),
                usage: el.getAttribute('data-usage') || el.getAttribute('data-value')
            }));
        }
        
        return data;
    """)
    
    if chart_data and len(chart_data) > 0:
        for item in chart_data:
            if item.get('period') and item.get('usage'):
                monthly_data.append(item)
    
    if monthly_data:
        starlink_data['monthly_usage'] = monthly_data
        print(f"✓ Monthly Data: Found {len(monthly_data)} periods")
        for period in monthly_data:
            print(f"  - {period['period']}: {period['usage_gb']} GB")
    else:
        print("⚠ Could not extract individual monthly data from chart")
        
except Exception as e:
    print(f"Could not extract monthly data: {e}")

# METHOD 4: Extract date range information
try:
    page_text = driver.find_element(By.TAG_NAME, "body").text
    
    # Look for date range (e.g., "May 17 - Jun 16")
    date_range_match = re.search(r'(\w+\s+\d+)\s*-\s*(\w+\s+\d+)', page_text)
    if date_range_match:
        starlink_data['billing_period_start'] = date_range_match.group(1)
        starlink_data['billing_period_end'] = date_range_match.group(2)
        print(f"✓ Billing Period: {starlink_data['billing_period_start']} to {starlink_data['billing_period_end']}")
    
    # Extract UTC notice
    if 'Data usage is tracked in UTC time' in page_text:
        starlink_data['timezone_note'] = 'UTC'
        print("✓ Timezone: UTC")
        
except Exception as e:
    print(f"Could not extract date range: {e}")

# Save all extracted data to CSV
timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
output_file = f'starlink_residential_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

try:
    # Prepare data for CSV
    csv_data = []
    
    # Add summary data
    csv_data.append({
        'data_type': 'summary',
        'metric': 'total_usage_gb',
        'value': starlink_data.get('total_usage_gb', 'N/A'),
        'timestamp': timestamp
    })
    
    csv_data.append({
        'data_type': 'summary',
        'metric': 'plan_type',
        'value': starlink_data.get('plan_type', 'N/A'),
        'timestamp': timestamp
    })
    
    csv_data.append({
        'data_type': 'summary',
        'metric': 'included_data_gb',
        'value': starlink_data.get('included_data_gb', 'N/A'),
        'timestamp': timestamp
    })
    
    csv_data.append({
        'data_type': 'summary',
        'metric': 'billing_period_start',
        'value': starlink_data.get('billing_period_start', 'N/A'),
        'timestamp': timestamp
    })
    
    csv_data.append({
        'data_type': 'summary',
        'metric': 'billing_period_end',
        'value': starlink_data.get('billing_period_end', 'N/A'),
        'timestamp': timestamp
    })
    
    # Add monthly data
    if 'monthly_usage' in starlink_data:
        for month_data in starlink_data['monthly_usage']:
            csv_data.append({
                'data_type': 'monthly',
                'metric': month_data.get('period', 'unknown'),
                'value': f"{month_data.get('usage_gb', 'N/A')} GB",
                'timestamp': timestamp
            })
    
    # Save to CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['data_type', 'metric', 'value', 'timestamp'])
        writer.writeheader()
        writer.writerows(csv_data)
    
    print(f"\n✅ Data saved to: {output_file}")
    
    # Also save as JSON for easier processing
    json_file = output_file.replace('.csv', '.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(starlink_data, f, indent=2)
    print(f"✅ Data also saved as JSON: {json_file}")
    
    # Display summary
    print("\n" + "="*50)
    print("EXTRACTED DATA SUMMARY")
    print("="*50)
    print(f"Total Usage: {starlink_data.get('total_usage_gb', 'N/A')} GB")
    print(f"Plan: {starlink_data.get('plan_type', 'N/A')}")
    print(f"Included Data: {starlink_data.get('included_data_gb', 'N/A')} GB")
    if 'billing_period_start' in starlink_data:
        print(f"Billing Period: {starlink_data['billing_period_start']} - {starlink_data['billing_period_end']}")
    
except Exception as e:
    print(f"Error saving data: {e}")

# Keep browser open for inspection if needed
print("\n" + "="*50)
print("To get MORE PRECISE data extraction:")
print("1. Right-click on the Total Data Usage number (355 GB)")
print("2. Select 'Inspect'")
print("3. Look for the HTML element's class name or ID")
print("4. Update the script with the exact selector")
print("="*50)

input("\nPress Enter to close the browser...")
driver.quit()