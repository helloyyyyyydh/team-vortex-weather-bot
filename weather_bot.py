
import os
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]
STATE_FILE = Path("seen_alerts.json")

KEYWORDS = (
    "tornado", "severe thunderstorm", "thunderstorm watch",
    "flash flood", "hurricane", "tropical storm", "typhoon",
    "cyclone", "winter storm", "blizzard", "flood warning",
    "high wind", "storm surge"
)

def send(message):
    requests.post(
        WEBHOOK,
        json={"content": message[:1900]},
        timeout=20
    ).raise_for_status()

def load_seen():
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text()))
    return set()

def save_seen(seen):
    STATE_FILE.write_text(json.dumps(sorted(seen)[-5000:]))

def main():
    seen = load_seen()
    first_run = not STATE_FILE.exists()
    current = set()

    # US National Weather Service alerts
    try:
        response = requests.get(
            "https://api.weather.gov/alerts/active",
            headers={"User-Agent": "TeamVortexWeatherBot/1.0"},
            timeout=25
        )
        response.raise_for_status()

        for alert in response.json().get("features", []):
            p = alert.get("properties", {})
            if p.get("status") != "Actual":
                continue

            title = p.get("event", "Weather alert")
            if not any(k in title.lower() for k in KEYWORDS):
                continue

            alert_id = alert.get("id", "")
            key = "nws:" + alert_id + ":" + str(p.get("sent", ""))

            if not alert_id:
                continue
            current.add(key)

            if key in seen or first_run:
                continue

            send(
                f"🌩️ **WEATHER ALERT: {title}**\n"
                f"📍 **Location:** {p.get('areaDesc', 'Not specified')}\n"
                f"🕒 **Starts:** {p.get('onset') or p.get('effective', 'Not specified')}\n"
                f"⌛ **Expires:** {p.get('expires', 'Not specified')}\n"
                f"📡 **Source:** US National Weather Service\n"
                f"🔗 {p.get('web') or alert_id}"
            )
            seen.add(key)

    except Exception as e:
        print("NWS check failed:", e)

    # GDACS global major-disaster alerts
    try:
        response = requests.get(
            "https://www.gdacs.org/xml/rss_24h.xml",
            timeout=25
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)

        for item in root.findall(".//item"):
            title = item.findtext("title") or "Global weather alert"
            description = item.findtext("description") or "See source"
            link = item.findtext("link") or ""
            pub_date = item.findtext("pubDate") or ""

            combined = (title + " " + description).lower()
            if not any(k in combined for k in KEYWORDS):
                continue

            key = "gdacs:" + (link or title) + ":" + pub_date
            current.add(key)

            if key in seen or first_run:
                continue

            send(
                f"🌍 **GLOBAL DISASTER ALERT: {title}**\n"
                f"📍 **Details:** {description[:700]}\n"
                f"🕒 **Reported:** {pub_date or 'Not specified'}\n"
                f"📡 **Source:** GDACS\n"
                f"🔗 {link}"
            )
            seen.add(key)

    except Exception as e:
        print("GDACS check failed:", e)

    if first_run:
        send(
            "🌪️ **TEAM VORTEX WEATHER BOT ONLINE!**\n"
            "Monitoring available US NWS alerts and major global "
            "disaster reports. Existing alerts were skipped on startup."
        )

    save_seen(seen)
    print("Weather check complete:", datetime.now(timezone.utc).isoformat())

if __name__ == "__main__":
    main()
