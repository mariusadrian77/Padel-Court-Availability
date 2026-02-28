"""
Availability monitor — runs on a schedule, detects newly opened slots,
and sends push notifications via ntfy.sh.
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from playwright.sync_api import sync_playwright

from notify import send_notification
from scraper import CLUBS, PadelScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
STATE_FILE = DATA_DIR / "state.json"

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        cfg = yaml.safe_load(f)

    if not cfg.get("ntfy_topic"):
        raise ValueError("ntfy_topic is required in config.yaml")
    if not cfg.get("watches"):
        raise ValueError("At least one watch entry is required in config.yaml")

    for i, watch in enumerate(cfg["watches"]):
        weekday = watch.get("weekday", "").lower()
        if weekday not in WEEKDAYS:
            raise ValueError(f"watches[{i}].weekday '{weekday}' is invalid. Use: {', '.join(WEEKDAYS)}")
        for club in watch.get("clubs", []):
            if club not in CLUBS:
                raise ValueError(f"watches[{i}] references unknown club '{club}'. Available: {', '.join(CLUBS)}")

    return cfg


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def upcoming_dates(weekday_name: str, weeks_ahead: int) -> list[str]:
    """Return the next N dates for a given weekday (e.g. next 4 Tuesdays)."""
    target = WEEKDAYS[weekday_name.lower()]
    today = datetime.now().date()
    days_until = (target - today.weekday()) % 7
    first = today + timedelta(days=days_until)

    dates = []
    for i in range(weeks_ahead):
        d = first + timedelta(weeks=i)
        if d >= today:
            dates.append(d.strftime("%Y-%m-%d"))
    return dates


def slot_in_window(slot_time: str, time_from: str, time_to: str) -> bool:
    """Check if a slot time (e.g. '18:00') falls within the watch window."""
    return time_from <= slot_time <= time_to


def build_booking_url(club_key: str, date: str, playing_times: int = 90) -> str:
    """Build a direct booking URL for a club + date."""
    config = CLUBS[club_key]
    return config["url_template"].format(
        base_url=config["base_url"],
        location=config["location"],
        date=date,
        playing_times=playing_times,
    )


def run_check(cfg: dict, state: dict, browser=None) -> dict:
    """Run one check cycle across all watches. Returns updated state."""
    ntfy_topic = cfg["ntfy_topic"]
    ntfy_server = cfg.get("ntfy_server", "https://ntfy.sh")
    playing_times = cfg.get("playing_times", 90)

    for watch in cfg["watches"]:
        clubs = watch["clubs"]
        weekday = watch["weekday"]
        time_from = watch["time_from"]
        time_to = watch["time_to"]
        weeks_ahead = watch.get("weeks_ahead", 4)

        dates = upcoming_dates(weekday, weeks_ahead)
        logger.info(
            f"Watch: {weekday} {time_from}-{time_to} | "
            f"Clubs: {', '.join(clubs)} | Dates: {', '.join(dates)}"
        )

        for club in clubs:
            for i, date in enumerate(dates):
                if i > 0:
                    time.sleep(2)
                state_key = f"{club}|{date}"

                try:
                    scraper = PadelScraper(club=club, date=date, playing_times=playing_times)
                    result = scraper.scrape_availability(browser=browser)
                except Exception as e:
                    if "Timeout" in str(e):
                        logger.warning(f"{CLUBS[club]['name']} on {date}: page timed out (date may not be bookable yet)")
                    else:
                        logger.error(f"Failed to scrape {club} for {date}: {e}")
                    continue

                matching = [
                    s for s in result["available_slots"]
                    if slot_in_window(s, time_from, time_to)
                ]

                club_name = CLUBS[club]["name"]
                if matching:
                    logger.info(f"{club_name} on {date}: {len(matching)} slot(s) in window: {', '.join(matching)}")
                else:
                    logger.info(f"{club_name} on {date}: no slots in {time_from}-{time_to}")

                previously_available = set(state.get(state_key, []))
                newly_available = [s for s in matching if s not in previously_available]

                if newly_available:
                    booking_url = build_booking_url(club, date, playing_times)
                    weekday_display = weekday.capitalize()
                    date_display = datetime.strptime(date, "%Y-%m-%d").strftime("%a %b %d")
                    slots_str = ", ".join(newly_available)

                    title = f"Padel slot opened - {club_name}"
                    message = (
                        f"{club_name}\n"
                        f"{weekday_display} {date_display}\n"
                        f"Slots: {slots_str} ({playing_times} min)\n"
                        f"\nBook now!"
                    )

                    logger.info(f"NEW SLOTS: {club_name} on {date}: {slots_str}")
                    send_notification(
                        topic=ntfy_topic,
                        title=title,
                        message=message,
                        server=ntfy_server,
                        click_url=booking_url,
                    )

                state[state_key] = matching

    return state


def main():
    config_path = os.environ.get("CONFIG_PATH", "config.yaml")
    logger.info(f"Loading config from {config_path}")
    cfg = load_config(config_path)

    interval = cfg.get("check_interval_minutes", 5)
    logger.info(f"Starting monitor - checking every {interval} minutes")
    logger.info(f"Notifications -> ntfy.sh topic: {cfg['ntfy_topic']}")
    logger.info(f"Watches: {len(cfg['watches'])}")

    state = load_state()

    while True:
        try:
            logger.info("Running check cycle...")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    state = run_check(cfg, state, browser=browser)
                finally:
                    browser.close()
            save_state(state)
            logger.info("Check cycle complete.")
        except Exception as e:
            logger.exception(f"Unexpected error during check cycle: {e}")

        logger.info(f"Sleeping {interval} minutes...")
        time.sleep(interval * 60)


if __name__ == "__main__":
    main()
