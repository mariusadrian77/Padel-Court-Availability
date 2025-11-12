"""
Web scraper for PadelCasa court availability checker.
Checks available time slots for padel courts in Utrecht.
"""

from playwright.sync_api import sync_playwright
from datetime import datetime
from typing import Dict
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
        self.time_pattern = re.compile(r'^\d{1,2}:\d{2}$')
    
    def build_url(self) -> str:
        """Build the booking URL with filters."""
        return (
            f"{self.base_url}#/court-booking/reservation"
            f"?location={self.location}"
            f"&date={self.date}"
            f"&playingTimes={self.playing_times}"
        )
    
    def _handle_age_confirmation(self, page):
        """Handle age confirmation dialog if present."""
        for selector in ["text='Yes I am'", "button:has-text('Ja')"]:
            try:
                page.wait_for_selector(selector, timeout=3000)
                page.click(selector)
                print("Age confirmation handled")
                return
            except:
                continue
    
    def _find_time_slots(self, page):
        """Find all time slot buttons on the page."""
        page.wait_for_selector(".timeslots-container", timeout=10000)
        page.wait_for_timeout(2000)  # Wait for slots to render
        
        container = page.query_selector(".timeslots-container")
        if container:
            buttons = container.query_selector_all("button")
            if buttons:
                print(f"Found {len(buttons)} time slot buttons")
                return buttons
        
        # Fallback if primary method fails
        raise Exception("Could not find time slots. Check debug files.")
    
    def _is_slot_available(self, slot):
        """Check if a time slot is available."""
        time_div = slot.query_selector("div")
        if not time_div:
            return None, None
        
        time_text = time_div.inner_text().strip()
        if not self.time_pattern.match(time_text):
            return None, None
        
        # Available if: not disabled AND no strikethrough
        is_disabled = slot.get_attribute("disabled") is not None
        has_strikethrough = "text-decoration-line-through" in (time_div.get_attribute("class") or "")
        has_disabled_class = "disabled" in (slot.get_attribute("class") or "")
        
        is_available = not is_disabled and not has_disabled_class and not has_strikethrough
        return time_text, is_available
    
    def scrape_availability(self) -> Dict:
        """
        Scrape court availability from the website.
        
        Returns:
            Dictionary containing available and booked time slots
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = context.new_page()
            
            try:
                print(f"Navigating to: {self.build_url()}")
                page.goto(self.build_url(), wait_until="networkidle", timeout=30000)
                
                self._handle_age_confirmation(page)
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(3000)
                
                time_slots = self._find_time_slots(page)
                
                available_slots = []
                booked_slots = []
                
                for slot in time_slots:
                    time_text, is_available = self._is_slot_available(slot)
                    if time_text:
                        if is_available:
                            available_slots.append(time_text)
                        else:
                            booked_slots.append(time_text)
                
                return {
                    "location": self.location,
                    "date": self.date,
                    "playing_times": self.playing_times,
                    "available_slots": sorted(available_slots),
                    "booked_slots": sorted(booked_slots),
                    "total_available": len(available_slots),
                    "total_booked": len(booked_slots)
                }
                
            except Exception as e:
                print(f"Error during scraping: {e}")
                page.screenshot(path="error_screenshot.png")
                raise
            finally:
                browser.close()


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
    result = scraper.scrape_availability()
    
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
        print("\nJSON Output:")
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
