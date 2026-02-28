"""
Web scraper for padel court availability.
Supports PadelCasa Utrecht, Peakz Padel Vechtsebanen, and Peakz Padel Zeehaenkade.
"""

from playwright.sync_api import sync_playwright
from datetime import datetime
from typing import Dict, List
import json
import re


CLUBS = {
    "padelcasa": {
        "name": "PadelCasa Utrecht",
        "base_url": "https://www.padelcasa.com/pages/utrecht",
        "location": "Utrecht",
        "url_template": "{base_url}#/court-booking/reservation?location={location}&date={date}&playingTimes={playing_times}",
        "age_confirmation": True,
        "court_type": None,
    },
    "peakz-vechtsebanen": {
        "name": "Peakz Padel Vechtsebanen",
        "base_url": "https://www.peakzpadel.nl/reserveren",
        "location": "vechtsebanen",
        "url_template": "{base_url}/court-booking/reservation?daypart=---&date={date}&location={location}",
        "age_confirmation": False,
        "court_type": "Double court indoor",
    },
    "peakz-zeehaenkade": {
        "name": "Peakz Padel Zeehaenkade",
        "base_url": "https://www.peakzpadel.nl/reserveren",
        "location": "Zeehaenkade",
        "url_template": "{base_url}/court-booking/reservation?daypart=---&date={date}&location={location}",
        "age_confirmation": False,
        "court_type": "Double court indoor",
    },
}


class PadelScraper:
    """Generic scraper for padel court availability using the shared booking widget."""

    def __init__(self, club: str, date: str = None, playing_times: int = 90):
        if club not in CLUBS:
            raise ValueError(f"Unknown club '{club}'. Available: {', '.join(CLUBS)}")

        config = CLUBS[club]
        self.club_key = club
        self.club_name = config["name"]
        self.base_url = config["base_url"]
        self.location = config["location"]
        self.url_template = config["url_template"]
        self.age_confirmation = config["age_confirmation"]
        self.court_type = config.get("court_type")
        self.date = date or datetime.now().strftime("%Y-%m-%d")
        self.playing_times = playing_times
        self.time_pattern = re.compile(r'^\d{1,2}:\d{2}$')

    def build_url(self) -> str:
        return self.url_template.format(
            base_url=self.base_url,
            location=self.location,
            date=self.date,
            playing_times=self.playing_times,
        )

    def _handle_age_confirmation(self, page):
        if not self.age_confirmation:
            return
        for selector in ["text='Yes I am'", "button:has-text('Ja')"]:
            try:
                page.wait_for_selector(selector, timeout=3000)
                page.click(selector)
                print("Age confirmation handled")
                return
            except:
                continue

    def _select_court_type(self, page):
        if not self.court_type:
            return
        try:
            multiselect = page.locator(".multiselect").filter(has_text="Type baan")
            multiselect.click()
            page.wait_for_timeout(500)
            option = page.locator(f".multiselect__option:has-text('{self.court_type}')")
            option.click()
            page.wait_for_timeout(2000)
            print(f"Court type filter set: {self.court_type}")
        except Exception as e:
            print(f"Warning: could not set court type filter: {e}")

    def _find_time_slots(self, page):
        page.wait_for_selector(".timeslots-container", timeout=15000)
        page.wait_for_timeout(2000)

        container = page.query_selector(".timeslots-container")
        if container:
            buttons = container.query_selector_all("button")
            if buttons:
                print(f"Found {len(buttons)} time slot buttons")
                return buttons

        raise Exception("Could not find time slots. Check debug files.")

    def _is_slot_available(self, slot):
        time_div = slot.query_selector("div")
        if not time_div:
            return None, None

        time_text = time_div.inner_text().strip()
        if not self.time_pattern.match(time_text):
            return None, None

        is_disabled = slot.get_attribute("disabled") is not None
        has_strikethrough = "text-decoration-line-through" in (time_div.get_attribute("class") or "")
        has_disabled_class = "disabled" in (slot.get_attribute("class") or "")

        is_available = not is_disabled and not has_disabled_class and not has_strikethrough
        return time_text, is_available

    def scrape_availability(self) -> Dict:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )
            page = context.new_page()

            try:
                url = self.build_url()
                print(f"Navigating to: {url}")
                page.goto(url, wait_until="networkidle", timeout=30000)

                self._handle_age_confirmation(page)
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(3000)

                self._select_court_type(page)

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
                    "club": self.club_name,
                    "location": self.location,
                    "date": self.date,
                    "playing_times": self.playing_times,
                    "available_slots": sorted(available_slots),
                    "booked_slots": sorted(booked_slots),
                    "total_available": len(available_slots),
                    "total_booked": len(booked_slots),
                }

            except Exception as e:
                print(f"Error scraping {self.club_name}: {e}")
                page.screenshot(path=f"error_{self.club_key}.png")
                raise
            finally:
                browser.close()


def scrape_all(clubs: List[str], date: str = None, playing_times: int = 90) -> List[Dict]:
    """Scrape availability for multiple clubs."""
    results = []
    for club in clubs:
        print(f"\n{'='*50}")
        print(f"Scraping: {CLUBS[club]['name']}")
        print(f"{'='*50}")
        try:
            scraper = PadelScraper(club=club, date=date, playing_times=playing_times)
            results.append(scraper.scrape_availability())
        except Exception as e:
            print(f"Failed to scrape {club}: {e}")
            results.append({"club": CLUBS[club]["name"], "error": str(e)})
    return results


def print_results(result: Dict):
    """Pretty-print results for a single club."""
    if "error" in result:
        print(f"\n  {result['club']}: FAILED - {result['error']}")
        return

    print(f"\n  Club: {result['club']}")
    print(f"  Date: {result['date']}")
    print(f"  Duration: {result['playing_times']} minutes")
    print(f"\n  Available slots ({result['total_available']}):")
    for slot in result['available_slots']:
        print(f"    + {slot}")
    print(f"\n  Booked slots ({result['total_booked']}):")
    for slot in result['booked_slots']:
        print(f"    - {slot}")


def main():
    import argparse

    club_names = ", ".join(CLUBS.keys())
    parser = argparse.ArgumentParser(description="Scrape padel court availability")
    parser.add_argument(
        "--club",
        nargs="+",
        choices=list(CLUBS.keys()) + ["all"],
        default=["all"],
        help=f"Club(s) to scrape. Available: {club_names}, all (default: all)",
    )
    parser.add_argument("--date", default=None, help="Date in YYYY-MM-DD format (default: today)")
    parser.add_argument("--playing-times", type=int, default=90, help="Playing duration in minutes")
    parser.add_argument("--output", default=None, help="Output JSON file path")

    args = parser.parse_args()

    clubs = list(CLUBS.keys()) if "all" in args.club else args.club
    date_display = args.date or datetime.now().strftime("%Y-%m-%d")

    print(f"Scraping {len(clubs)} club(s) for {date_display} ({args.playing_times} min)")
    results = scrape_all(clubs=clubs, date=args.date, playing_times=args.playing_times)

    print("\n" + "=" * 60)
    print("AVAILABILITY RESULTS")
    print("=" * 60)
    for result in results:
        print_results(result)
        print(f"\n  {'-'*40}")
    print("=" * 60)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to {args.output}")
    else:
        print("\nJSON Output:")
        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
