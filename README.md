# Padel Court Availability Scraper

A web scraper for checking padel court availability on [PadelCasa Utrecht](https://www.padelcasa.com/pages/utrecht).

## Features

- Scrapes court availability for specific dates and durations
- Identifies available vs booked time slots
- Supports custom filters (location, date, playing duration)
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

### Basic Usage

Check availability for today with default settings (Utrecht, 90 minutes):
```bash
python scraper.py
```

### Custom Date and Filters

Check availability for a specific date:
```bash
python scraper.py --date 2025-11-19 --playing-times 90
```

### Save Results to File

Save results to a JSON file:
```bash
python scraper.py --date 2025-11-19 --output results.json
```

### Command Line Options

- `--location`: Location name (default: "Utrecht")
- `--date`: Date in YYYY-MM-DD format (default: today)
- `--playing-times`: Playing duration in minutes (default: 90)
- `--output`: Output JSON file path (optional)

### Example Output

```
AVAILABILITY RESULTS
==================================================
Location: Utrecht
Date: 2025-11-19
Duration: 90 minutes

Available slots (8):
  ✓ 08:00
  ✓ 08:30
  ✓ 09:00
  ✓ 09:30
  ✓ 10:00
  ✓ 10:30
  ✓ 11:30
  ✓ 14:30

Booked slots (15):
  ✗ 11:00
  ✗ 12:00
  ✗ 12:30
  ✗ 13:00
  ...
==================================================
```

## How It Works

The scraper uses Playwright to:
1. Navigate to the PadelCasa booking page with the specified filters
2. Wait for the page to fully load (including JavaScript rendering)
3. Find all time slot elements in the "SELECTEER STARTTIJD" section
4. Determine availability by checking:
   - Visual indicators (opacity, color, strikethrough)
   - CSS classes
   - Disabled state
   - Cursor style

Available slots are identified as those that are:
- Not disabled
- Not greyed out
- Not cut/strikethrough
- Have normal opacity and pointer cursor

## Using as a Python Module

You can also import and use the scraper in your own Python code:

```python
from scraper import PadelCasaScraper

# Create scraper instance
scraper = PadelCasaScraper(
    location="Utrecht",
    date="2025-11-19",
    playing_times=90
)

# Get availability
results = scraper.get_availability()

# Access results
print(f"Available slots: {results['available_slots']}")
print(f"Booked slots: {results['booked_slots']}")
```

## Requirements

All dependencies are listed in `requirements.txt` and have been installed in the `padel-env` conda environment.

## Notes

- The scraper runs in headless mode by default. To debug, change `headless=True` to `headless=False` in `scraper.py`
- The website may require age confirmation - the scraper handles this automatically
- Network timeouts are set to 30 seconds - adjust if needed for slower connections
