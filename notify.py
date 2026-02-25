"""Push notifications via ntfy.sh."""

import logging
import requests

logger = logging.getLogger(__name__)

DEFAULT_SERVER = "https://ntfy.sh"


def send_notification(
    topic: str,
    title: str,
    message: str,
    server: str = DEFAULT_SERVER,
    priority: str = "high",
    tags: str = "tennis",
    click_url: str = None,
):
    headers = {
        "Title": title,
        "Priority": priority,
        "Tags": tags,
    }
    if click_url:
        headers["Click"] = click_url

    try:
        resp = requests.post(
            f"{server.rstrip('/')}/{topic}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        logger.info(f"Notification sent: {title}")
    except requests.RequestException as e:
        logger.error(f"Failed to send notification: {e}")
