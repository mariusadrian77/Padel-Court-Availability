"""
Web scraper for padel court availability.
Supports PadelCasa Utrecht, Peakz Padel Vechtsebanen, and Peakz Padel Zeehaenkade.
"""

import argparse
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

from playwright.sync_api import Browser, sync_playwright

logger = logging.getLogger(__name__)


CLUBS = {
    "padelcasa": {
        "name": "PadelCasa Utrecht",
        "base_url": "https://www.padelcasa.com/pages/utrecht",
        "location": "Utrecht",
        "url_template": "{base_url}#/court-booking/reservation?location={location}&date={date}&playingTimes={playing_times}",
        "age_confirmation": True,
        "court_type": None,
        "has_filters": False,
    },
    "peakz-vechtsebanen": {
        "name": "Peakz Padel Vechtsebanen",
        "base_url": "https://www.peakzpadel.nl/reserveren",
        "location": "vechtsebanen",
        "url_template": "{base_url}/court-booking/reservation?daypart=---&date={date}&location={location}",
        "age_confirmation": False,
        "court_type": "Double court indoor",
        "has_filters": True,
    },
    "peakz-zeehaenkade": {
        "name": "Peakz Padel Zeehaenkade",
        "base_url": "https://www.peakzpadel.nl/reserveren",
        "location": "Zeehaenkade",
        "url_template": "{base_url}/court-booking/reservation?daypart=---&date={date}&location={location}",
        "age_confirmation": False,
        "court_type": "Double court indoor",
        "has_filters": True,
    },
}

TIME_PATTERN = re.compile(r'^\d{1,2}:\d{2}$')


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
        self.has_filters = config.get("has_filters", False)
        self.date = date or datetime.now().strftime("%Y-%m-%d")
        self.playing_times = playing_times

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
                logger.debug("Age confirmation handled")
                return
            except Exception:
                continue

    def _select_filter(self, page, filter_label: str, option_text: str):
        try:
            multiselect = page.locator(".multiselect").filter(has_text=filter_label)
            multiselect.click()
            page.wait_for_timeout(300)
            option = page.locator(f".multiselect__option:has-text('{option_text}')")
            option.click()
            page.wait_for_timeout(2000)
            logger.debug(f"Filter '{filter_label}' set to: {option_text}")
        except Exception as e:
            logger.warning(f"Could not set filter '{filter_label}' to '{option_text}': {e}")

    def _apply_filters(self, page):
        if not self.has_filters:
            return
        if self.court_type:
            self._select_filter(page, "Type baan", self.court_type)
        self._select_filter(page, "Speeltijd", f"{self.playing_times} min")

    def _wait_for_slots(self, page):
        page.wait_for_selector(".timeslots-container", timeout=15000)
        page.locator(".timeslots-container button").first.wait_for(timeout=5000)

    def _read_time_slots(self, page) -> tuple[list[str], list[str]]:
        container = page.query_selector(".timeslots-container")
        if not container:
            raise Exception("Could not find time slots container.")

        buttons = container.query_selector_all("button")
        logger.debug(f"Found {len(buttons)} time slot buttons")

        available_slots = []
        booked_slots = []

        for slot in buttons:
            time_div = slot.query_selector("div")
            if not time_div:
                continue
            time_text = time_div.inner_text().strip()
            if not TIME_PATTERN.match(time_text):
                continue

            is_disabled = slot.get_attribute("disabled") is not None
            has_strikethrough = "text-decoration-line-through" in (time_div.get_attribute("class") or "")
            has_disabled_class = "disabled" in (slot.get_attribute("class") or "")

            if not is_disabled and not has_disabled_class and not has_strikethrough:
                available_slots.append(time_text)
            else:
                booked_slots.append(time_text)

        return sorted(available_slots), sorted(booked_slots)

    def scrape_availability(self, browser: Optional[Browser] = None) -> Dict:
        owns_browser = browser is None
        pw_context = None

        if owns_browser:
            pw_context = sync_playwright().start()
            browser = pw_context.chromium.launch(headless=True)

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        page = context.new_page()

        try:
            url = self.build_url()
            logger.info(f"Scraping {self.club_name} for {self.date}")
            page.goto(url, wait_until="networkidle", timeout=30000)

            self._handle_age_confirmation(page)
            self._wait_for_slots(page)

            self._apply_filters(page)

            available_slots, booked_slots = self._read_time_slots(page)

            return {
                "club": self.club_name,
                "location": self.location,
                "date": self.date,
                "playing_times": self.playing_times,
                "available_slots": available_slots,
                "booked_slots": booked_slots,
                "total_available": len(available_slots),
                "total_booked": len(booked_slots),
            }

        except Exception as e:
            logger.error(f"Error scraping {self.club_name}: {e}")
            try:
                page.screenshot(path=f"error_{self.club_key}.png")
            except Exception:
                pass
            raise
        finally:
            context.close()
            if owns_browser:
                browser.close()
                if pw_context:
                    pw_context.stop()


def scrape_all(clubs: List[str], date: str = None, playing_times: int = 90) -> List[Dict]:
    """Scrape availability for multiple clubs, reusing a single browser instance."""
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for club in clubs:
                try:
                    scraper = PadelScraper(club=club, date=date, playing_times=playing_times)
                    results.append(scraper.scrape_availability(browser=browser))
                except Exception as e:
                    logger.error(f"Failed to scrape {club}: {e}")
                    results.append({"club": CLUBS[club]["name"], "error": str(e)})
        finally:
            browser.close()
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
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

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
