# Padel Court Availability Scraper

A web scraper for checking padel court availability across multiple clubs in Utrecht.

## Supported Clubs

| Key | Club | Website |
|-----|------|---------|
| `padelcasa` | PadelCasa Utrecht | [padelcasa.com](https://www.padelcasa.com/pages/utrecht) |
| `peakz-vechtsebanen` | Peakz Padel Vechtsebanen | [peakzpadel.nl](https://www.peakzpadel.nl/reserveren/court-booking/reservation?location=vechtsebanen) |
| `peakz-zeehaenkade` | Peakz Padel Zeehaenkade | [peakzpadel.nl](https://www.peakzpadel.nl/reserveren/court-booking/reservation?location=Zeehaenkade) |

## Features

- Scrapes court availability for specific dates and durations
- Supports multiple clubs in a single run
- Identifies available vs booked time slots
- Gracefully handles failures per club (one failing won't stop the rest)
- Outputs results in JSON format

## Installation

1. Make sure you have Python 3.11 installed (the project uses a conda environment)

2. Activate the conda environment:
   ```bash
   conda activate padel-env
   ```

3. Install Playwright browsers (required for web scraping):
   ```bash
   playwright install chromium
   ```

## Usage

### Scrape All Clubs

Check availability across all supported clubs for today (90 minutes):
```bash
python scraper.py
```

### Scrape Specific Clubs

Scrape only the Peakz locations:
```bash
python scraper.py --club peakz-vechtsebanen peakz-zeehaenkade --date 2026-02-25
```

Scrape only PadelCasa:
```bash
python scraper.py --club padelcasa --date 2026-02-25
```

### Save Results to File

```bash
python scraper.py --date 2026-02-25 --output results.json
```

### Command Line Options

- `--club`: Club(s) to scrape (default: `all`). Available: `padelcasa`, `peakz-vechtsebanen`, `peakz-zeehaenkade`, `all`
- `--date`: Date in YYYY-MM-DD format (default: today)
- `--playing-times`: Playing duration in minutes (default: 90)
- `--output`: Output JSON file path (optional)

### Example Output

```
Scraping 3 club(s) for 2026-02-25 (90 min)

============================================================
AVAILABILITY RESULTS
============================================================

  Club: PadelCasa Utrecht
  Date: 2026-02-25
  Duration: 90 minutes

  Available slots (8):
    ✓ 08:00
    ✓ 08:30
    ✓ 09:00
    ...

  Booked slots (15):
    ✗ 11:00
    ✗ 12:00
    ...

  ----------------------------------------

  Club: Peakz Padel Vechtsebanen
  Date: 2026-02-25
  Duration: 90 minutes

  Available slots (5):
    ✓ 09:00
    ✓ 09:30
    ...

  ----------------------------------------
============================================================
```

## How It Works

The scraper uses Playwright to:
1. Navigate to each club's booking page with the specified filters
2. Wait for the page to fully load (including JavaScript rendering)
3. Handle any confirmation dialogs (e.g. age confirmation on PadelCasa)
4. Find all time slot buttons in the `.timeslots-container` element
5. Determine availability by checking the disabled state, CSS classes, and strikethrough styling

## Using as a Python Module

```python
from scraper import PadelScraper, scrape_all

# Scrape a single club
scraper = PadelScraper(club="peakz-vechtsebanen", date="2026-02-25", playing_times=90)
result = scraper.scrape_availability()
print(f"Available: {result['available_slots']}")

# Scrape multiple clubs
results = scrape_all(
    clubs=["padelcasa", "peakz-vechtsebanen", "peakz-zeehaenkade"],
    date="2026-02-25",
    playing_times=90,
)
for r in results:
    print(f"{r['club']}: {r['total_available']} available")
```

## Adding a New Club

To add another club that uses the same booking widget, add an entry to the `CLUBS` dictionary in `scraper.py`:

```python
CLUBS = {
    ...
    "new-club": {
        "name": "New Club Name",
        "base_url": "https://www.example.com/booking",
        "location": "location-param",
        "url_template": "{base_url}/court-booking/reservation?date={date}&location={location}",
        "age_confirmation": False,
    },
}
```

## Requirements

All dependencies are listed in `requirements.txt` and have been installed in the `padel-env` conda environment.

## Notes

- The scraper runs in headless mode by default. To debug, change `headless=True` to `headless=False` in `scraper.py`
- PadelCasa may show an age confirmation dialog — the scraper handles this automatically
- Network timeouts are set to 30 seconds — adjust if needed for slower connections
- If a club fails to scrape, the error is captured and the remaining clubs continue
