# Padel Court Availability Monitor

Monitors padel court availability across multiple clubs in Utrecht and sends push notifications when a matching slot opens up. Designed to run on a NAS via Docker.

## Supported Clubs

| Key | Club | Website |
|-----|------|---------|
| `padelcasa` | PadelCasa Utrecht | [padelcasa.com](https://www.padelcasa.com/pages/utrecht) |
| `peakz-vechtsebanen` | Peakz Padel Vechtsebanen | [peakzpadel.nl](https://www.peakzpadel.nl/reserveren/court-booking/reservation?location=vechtsebanen) |
| `peakz-zeehaenkade` | Peakz Padel Zeehaenkade | [peakzpadel.nl](https://www.peakzpadel.nl/reserveren/court-booking/reservation?location=Zeehaenkade) |

## Features

- Periodically scrapes court availability (configurable interval, default 5 min)
- Watches for specific weekday + time window combinations (e.g. Tuesdays 18:00-19:00)
- Detects **newly opened** slots and sends push notifications via [ntfy.sh](https://ntfy.sh)
- Notifications include a direct booking link
- Supports multiple clubs and multiple watch rules
- Persists state across restarts so you only get notified once per new slot
- Runs in Docker — set it and forget it

## Quick Start (Docker)

1. Clone the repo on your NAS:

```bash
git clone <repo-url>
cd Padel-Court-Availability
```

2. Copy and edit the config:

```bash
cp config.example.yaml config.yaml
nano config.yaml
```

3. Set your ntfy topic and watch rules in `config.yaml`:

```yaml
check_interval_minutes: 5
playing_times: 90
ntfy_topic: "padel-your-secret-topic"

watches:
  - clubs: ["peakz-vechtsebanen", "peakz-zeehaenkade", "padelcasa"]
    weekday: "tuesday"
    time_from: "18:00"
    time_to: "19:00"
    weeks_ahead: 4
```

4. Install the [ntfy app](https://ntfy.sh) on your phone and subscribe to your topic.

5. Start the monitor:

```bash
docker compose up -d
```

6. Check logs:

```bash
docker compose logs -f
```

## Configuration

All configuration lives in `config.yaml` (not committed to git).

| Field | Description | Default |
|-------|-------------|---------|
| `check_interval_minutes` | How often to check (minutes) | `5` |
| `playing_times` | Slot duration in minutes | `90` |
| `ntfy_topic` | Your ntfy.sh topic name (acts as password) | *required* |
| `ntfy_server` | ntfy server URL | `https://ntfy.sh` |

Each entry in `watches` defines what to look for:

| Field | Description | Example |
|-------|-------------|---------|
| `clubs` | List of club keys to check | `["padelcasa"]` |
| `weekday` | Day of the week | `"tuesday"` |
| `time_from` | Start of time window | `"18:00"` |
| `time_to` | End of time window | `"19:00"` |
| `weeks_ahead` | How many upcoming matching days to check | `4` |

You can add as many watch entries as you like.

## Notification Behavior

- You only get notified when a slot **newly becomes available** — not every 5 minutes for the same open slot
- If a slot disappears and later reappears, you get notified again
- Each notification includes the club name, date, time slot(s), and a tap-to-book link

## Standalone Scraper (CLI)

The scraper can also be used independently without the monitor:

```bash
# Scrape all clubs for today
python scraper.py

# Scrape specific clubs
python scraper.py --club peakz-vechtsebanen peakz-zeehaenkade --date 2026-03-03

# Save to file
python scraper.py --output results.json
```

CLI options: `--club`, `--date`, `--playing-times`, `--output`.

## Using as a Python Module

```python
from scraper import PadelScraper, scrape_all

# Single club
scraper = PadelScraper(club="peakz-vechtsebanen", date="2026-03-03", playing_times=90)
result = scraper.scrape_availability()

# Multiple clubs
results = scrape_all(
    clubs=["padelcasa", "peakz-vechtsebanen", "peakz-zeehaenkade"],
    date="2026-03-03",
)
```

## Adding a New Club

Add an entry to the `CLUBS` dictionary in `scraper.py`:

```python
"new-club": {
    "name": "New Club Name",
    "base_url": "https://www.example.com/booking",
    "location": "location-param",
    "url_template": "{base_url}/court-booking/reservation?date={date}&location={location}",
    "age_confirmation": False,
},
```

Then reference `"new-club"` in your `config.yaml` watches.

## Project Structure

```
scraper.py           # Playwright-based court availability scraper
monitor.py           # Scheduler: periodic checks, state diffing, notifications
notify.py            # ntfy.sh push notification helper
config.example.yaml  # Example configuration (edit and save as config.yaml)
Dockerfile           # Container image (Playwright + Chromium included)
docker-compose.yml   # Docker Compose service definition
requirements.txt     # Python dependencies
```

## Local Development

```bash
pip install -r requirements.txt
playwright install chromium
cp config.example.yaml config.yaml
python monitor.py
```

## Notes

- The Docker image uses `mcr.microsoft.com/playwright/python:v1.40.0-jammy` which includes Chromium — no need for `playwright install`
- State is persisted in a Docker volume (`padel-data`) so restarts don't re-trigger old notifications
- The container timezone is set to `Europe/Amsterdam` via `docker-compose.yml`
- If a club fails to scrape, the error is logged and the remaining clubs continue
- PadelCasa may show an age confirmation dialog — handled automatically
