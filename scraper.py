"""
Web scraper for PadelCasa court availability checker.
Checks available time slots for padel courts in Utrecht.
"""

from playwright.sync_api import sync_playwright
from datetime import datetime
from typing import List, Dict
import json
import re


class PadelCasaScraper:
    """Scraper for PadelCasa court availability."""
    
    def __init__(self, location: str = "Utrecht", date: str = None, playing_times: int = 90):
        """
        Initialize the scraper.
        
        Args:
            location: Location name (default: "Utrecht")
            date: Date in YYYY-MM-DD format (default: today)
            playing_times: Playing duration in minutes (default: 90)
        """
        self.location = location
        self.date = date or datetime.now().strftime("%Y-%m-%d")
        self.playing_times = playing_times
        self.base_url = "https://www.padelcasa.com/pages/utrecht"
        
    def build_url(self) -> str:
        """Build the booking URL with filters."""
        return (
            f"{self.base_url}#/court-booking/reservation"
            f"?location={self.location}"
            f"&date={self.date}"
            f"&playingTimes={self.playing_times}"
        )
    
    def scrape_availability(self) -> Dict:
        """
        Scrape court availability from the website.
        
        Returns:
            Dictionary containing available and booked time slots
        """
        with sync_playwright() as p:
            # Launch browser (headless=False for debugging, set to True for production)
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = context.new_page()
            
            try:
                # Navigate to the booking page
                url = self.build_url()
                print(f"Navigating to: {url}")
                page.goto(url, wait_until="networkidle", timeout=30000)
                
                # Wait for the age confirmation dialog and handle it if present
                try:
                    age_confirm_selectors = [
                        "text='Yes I am'",
                        "button:has-text('Yes I am')",
                        "button:has-text('Ja')",  # Dutch version
                        "[data-testid*='age']",
                    ]
                    for selector in age_confirm_selectors:
                        try:
                            page.wait_for_selector(selector, timeout=3000)
                            page.click(selector)
                            print("Age confirmation handled")
                            break
                        except:
                            continue
                except:
                    print("No age confirmation dialog found")
                
                # Wait for page to be interactive
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(3000)  # Give JavaScript time to render
                
                # Try to find the time slots section - be flexible with selectors
                time_section_found = False
                time_section_selectors = [
                    "text='SELECTEER STARTTIJD'",
                    "text='Selecteer starttijd'",
                    "text='Selecteer Starttijd'",
                    "[class*='starttijd']",
                    "[class*='start-tijd']",
                    "[class*='time-slot']",
                    "[class*='timeslot']",
                ]
                
                for selector in time_section_selectors:
                    try:
                        page.wait_for_selector(selector, timeout=5000)
                        print(f"Found time section with selector: {selector}")
                        time_section_found = True
                        break
                    except:
                        continue
                
                if not time_section_found:
                    print("Warning: Could not find time section header, proceeding anyway...")
                    # Take a screenshot for debugging
                    page.screenshot(path="debug_page_load.png")
                    print("Screenshot saved to debug_page_load.png")
                
                # Wait for the timeslots container to be visible
                try:
                    page.wait_for_selector(".timeslots-container", timeout=10000)
                    print("Timeslots container found")
                except:
                    print("Warning: .timeslots-container not found within timeout, proceeding anyway...")
                
                # Wait a bit more for all time slots to render
                page.wait_for_timeout(2000)
                
                # Find all time slot buttons
                # Based on the HTML structure: buttons are in .timeslots-container
                # Available slots: button without disabled attribute, time div without text-decoration-line-through
                # Booked slots: button with disabled attribute, time div with text-decoration-line-through class
                
                time_slots = []
                time_pattern = re.compile(r'^\d{1,2}:\d{2}$')
                
                print("Searching for time slot elements...")
                
                # Strategy 1: Look for .timeslots-container (most reliable based on HTML structure)
                try:
                    timeslots_container = page.query_selector(".timeslots-container")
                    if timeslots_container:
                        buttons = timeslots_container.query_selector_all("button")
                        time_slots = buttons
                        print(f"Found {len(time_slots)} time slot buttons in .timeslots-container")
                    else:
                        print("Warning: .timeslots-container not found, trying alternative methods...")
                except Exception as e:
                    print(f"Error finding .timeslots-container: {e}")
                
                # Strategy 2: Fallback - find buttons with time patterns
                if len(time_slots) == 0:
                    print("Trying alternative search methods...")
                    all_buttons = page.query_selector_all("button.btn-outline-primary")
                    for button in all_buttons:
                        try:
                            # Get the first div inside the button (contains the time)
                            time_div = button.query_selector("div")
                            if time_div:
                                text = time_div.inner_text().strip()
                                if time_pattern.match(text):
                                    time_slots.append(button)
                        except:
                            continue
                    print(f"Found {len(time_slots)} time slot buttons (alternative method)")
                
                # Strategy 3: Last resort - search all buttons
                if len(time_slots) == 0:
                    print("Trying comprehensive search...")
                    all_buttons = page.query_selector_all("button")
                    for button in all_buttons:
                        try:
                            # Check if button contains a time pattern
                            text = button.inner_text().strip()
                            # Extract just the time part (first line usually)
                            first_line = text.split('\n')[0].strip()
                            if time_pattern.match(first_line):
                                time_slots.append(button)
                        except:
                            continue
                    print(f"Found {len(time_slots)} time slot buttons (comprehensive search)")
                
                if len(time_slots) == 0:
                    # Take a screenshot and save page HTML for debugging
                    page.screenshot(path="debug_no_slots.png")
                    html_content = page.content()
                    with open("debug_page.html", "w", encoding="utf-8") as f:
                        f.write(html_content)
                    print("Debug files saved: debug_no_slots.png, debug_page.html")
                    raise Exception("Could not find any time slots on the page. Check debug files.")
                
                available_slots = []
                booked_slots = []
                
                for slot in time_slots:
                    try:
                        # Extract time from the first div inside the button
                        # The structure is: <button><div>08:00</div><hr><div>€36,00</div></button>
                        time_div = slot.query_selector("div")
                        if not time_div:
                            continue
                        
                        time_text = time_div.inner_text().strip()
                        
                        # Check if it's a valid time format (HH:MM)
                        if not time_pattern.match(time_text):
                            continue
                        
                        # Check if the slot is available or booked
                        # Based on HTML structure:
                        # - Available: button without disabled attribute, time div without text-decoration-line-through class
                        # - Booked: button with disabled attribute, time div with text-decoration-line-through class
                        
                        is_disabled = slot.get_attribute("disabled") is not None
                        slot_classes = slot.get_attribute("class") or ""
                        time_div_classes = time_div.get_attribute("class") or ""
                        
                        # Check for strikethrough class on the time div
                        has_strikethrough_class = "text-decoration-line-through" in time_div_classes
                        
                        # Check if button has disabled class
                        has_disabled_class = "disabled" in slot_classes
                        
                        # Available if: not disabled AND no strikethrough on time
                        is_available = not is_disabled and not has_disabled_class and not has_strikethrough_class
                        
                        if is_available:
                            available_slots.append(time_text)
                        else:
                            booked_slots.append(time_text)
                            
                        print(f"Time slot {time_text}: {'Available' if is_available else 'Booked'}")
                            
                    except Exception as e:
                        # Skip elements that don't match our criteria
                        print(f"Error processing slot: {e}")
                        continue
                
                result = {
                    "location": self.location,
                    "date": self.date,
                    "playing_times": self.playing_times,
                    "available_slots": sorted(available_slots),
                    "booked_slots": sorted(booked_slots),
                    "total_available": len(available_slots),
                    "total_booked": len(booked_slots)
                }
                
                return result
                
            except Exception as e:
                print(f"Error during scraping: {e}")
                # Take a screenshot for debugging
                page.screenshot(path="error_screenshot.png")
                raise
            finally:
                browser.close()
    
    def get_availability(self) -> Dict:
        """Convenience method to get availability."""
        return self.scrape_availability()


def main():
    """Main function to run the scraper."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape PadelCasa court availability")
    parser.add_argument("--location", default="Utrecht", help="Location name")
    parser.add_argument("--date", default=None, help="Date in YYYY-MM-DD format")
    parser.add_argument("--playing-times", type=int, default=90, help="Playing duration in minutes")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    
    args = parser.parse_args()
    
    scraper = PadelCasaScraper(
        location=args.location,
        date=args.date,
        playing_times=args.playing_times
    )
    
    print(f"Scraping availability for {args.location} on {args.date or 'today'} ({args.playing_times} minutes)")
    result = scraper.get_availability()
    
    # Print results
    print("\n" + "="*50)
    print("AVAILABILITY RESULTS")
    print("="*50)
    print(f"Location: {result['location']}")
    print(f"Date: {result['date']}")
    print(f"Duration: {result['playing_times']} minutes")
    print(f"\nAvailable slots ({result['total_available']}):")
    for slot in result['available_slots']:
        print(f"  ✓ {slot}")
    print(f"\nBooked slots ({result['total_booked']}):")
    for slot in result['booked_slots']:
        print(f"  ✗ {slot}")
    print("="*50)
    
    # Save to file if requested
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to {args.output}")
    else:
        # Print JSON to stdout
        print("\nJSON Output:")
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

