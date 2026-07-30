import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN")
if not token:
    print("Error: TELEGRAM_BOT_TOKEN not set in .env")
    sys.exit(1)

url = sys.argv[1] if len(sys.argv) > 1 else input("Enter webhook URL (e.g. https://your-app.vercel.app/webhook): ")

resp = requests.post(
    f"https://api.telegram.org/bot{token}/setWebhook",
    json={"url": url}
)
print(resp.json())
