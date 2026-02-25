FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scraper.py notify.py monitor.py ./

ENV DATA_DIR=/app/data
ENV CONFIG_PATH=/app/config.yaml

CMD ["python", "-u", "monitor.py"]
