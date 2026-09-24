import os
import re
import asyncio
import threading
from datetime import datetime, time
from zoneinfo import ZoneInfo

import requests
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION_STRING = os.environ["TELEGRAM_SESSION"]

BOT_TOKEN = os.environ["BOT_TOKEN"]

# Your chat ID
BOT_CHAT_ID = os.environ["BOT_CHAT_ID"]

# Friend's chat ID
FRIEND_CHAT_ID = os.environ["FRIEND_CHAT_ID"]


# ============================================================
# NOTIFICATION RECIPIENTS
# ============================================================

BOT_CHAT_IDS = [
    BOT_CHAT_ID,
    FRIEND_CHAT_ID,
]


# ============================================================
# SETTINGS
# ============================================================

TARGET_GROUP = "@colorwizclub2"

TARGET_TYPES = {
    "PARITY",
    "SAPRE",
    "BCONE",
    "EMERD",
}


# ============================================================
# EXACT AMOUNTS TO ALERT
# ============================================================

ALLOWED_AMOUNTS = {
    90,
    270,
    810,
    2430,
    7290,

    900,
    2700,
    8100,
    24300,
    72900,

    9000,
    27000,
    81000,
    243000,
    729000,
}


# ============================================================
# MONITORING TIME
# ============================================================

IST = ZoneInfo("Asia/Kolkata")

START_TIME = time(7, 0, 0)
END_TIME = time(12, 0, 0)


# ============================================================
# FLASK SERVER
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Telegram watcher is running."


@app.route("/health")
def health():
    return "OK"


def run_flask():
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        debug=False,
        use_reloader=False,
    )


# ============================================================
# TELEGRAM CLIENT
# ============================================================

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH,
)


# ============================================================
# TIME CHECK
# ============================================================

def is_allowed_time(message_time):
    current_time = message_time.time()

    return START_TIME <= current_time < END_TIME


# ============================================================
# MESSAGE PARSER
# ============================================================

def extract_target_content(text):

    if not text:
        return None

    normalized = text.upper().strip()

    found_type = None
    type_position = -1

    # Find target type
    for target_type in TARGET_TYPES:

        match = re.search(
            rf"\b{re.escape(target_type)}\b",
            normalized,
        )

        if match:

            found_type = target_type
            type_position = match.end()

            break

    if not found_type:
        return None

    # Text after the target type
    remaining_text = normalized[type_position:]

    # Find first number after the target type
    amount_match = re.search(
        r"\b(\d+(?:\.\d+)?)\b",
        remaining_text,
    )

    if not amount_match:
        return None

    amount_text = amount_match.group(1)

    try:
        amount = float(amount_text)

    except ValueError:
        return None

    # Only whole numbers are allowed
    if not amount.is_integer():
        return None

    amount = int(amount)

    return {
        "type": found_type,
        "amount": amount,
        "raw_text": text,
    }


# ============================================================
# SEND TELEGRAM BOT ALERT
# ============================================================

def send_bot_notification(
    target_type,
    amount,
    message_text,
    message_time,
):

    url = (
        f"https://api.telegram.org/bot"
        f"{BOT_TOKEN}/sendMessage"
    )

    notification = (
        "🚨 ALERT\n\n"
        f"Type: {target_type}\n"
        f"Amount: {amount}\n"
        f"Time: {message_time.strftime('%H:%M:%S')} IST\n\n"
        f"{target_type} 🔴 {amount}"
    )

    # Send the same alert to both users
    for chat_id in BOT_CHAT_IDS:

        payload = {
            "chat_id": chat_id,
            "text": notification,
        }

        try:

            response = requests.post(
                url,
                json=payload,
                timeout=15,
            )

            if response.ok:

                print(
                    f"✅ Alert sent to {chat_id}: "
                    f"{target_type} {amount}",
                    flush=True,
                )

            else:

                print(
                    f"❌ Bot API error for {chat_id}: "
                    f"{response.status_code} "
                    f"{response.text}",
                    flush=True,
                )

        except Exception as e:

            print(
                f"❌ Notification error for {chat_id}: "
                f"{e}",
                flush=True,
            )


# ============================================================
# NEW MESSAGE HANDLER
# ============================================================

@client.on(events.NewMessage(chats=TARGET_GROUP))
async def new_message_handler(event):

    try:

        # ----------------------------------------------------
        # Convert Telegram message time to IST
        # ----------------------------------------------------

        message_time = event.message.date.astimezone(IST)

        # ----------------------------------------------------
        # Only monitor 07:00 - 12:00 IST
        # ----------------------------------------------------

        if not is_allowed_time(message_time):
            return

        # ----------------------------------------------------
        # Get message text
        # ----------------------------------------------------

        text = event.raw_text

        if not text:
            return

        # ----------------------------------------------------
        # Extract type + amount
        # ----------------------------------------------------

        result = extract_target_content(text)

        if not result:
            return

        target_type = result["type"]
        amount = result["amount"]

        # ----------------------------------------------------
        # EXACT AMOUNT CHECK
        # ----------------------------------------------------

        if amount not in ALLOWED_AMOUNTS:
            return

        # ----------------------------------------------------
        # MATCH FOUND
        # ----------------------------------------------------

        print(
            "\n🚨 MATCH FOUND",
            flush=True,
        )

        print(
            f"Type: {target_type}",
            flush=True,
        )

        print(
            f"Amount: {amount}",
            flush=True,
        )

        print(
            f"Time: "
            f"{message_time.strftime('%H:%M:%S')} IST",
            flush=True,
        )

        print(
            f"Message: {text}",
            flush=True,
        )

        # ----------------------------------------------------
        # Send to YOU + FRIEND
        # ----------------------------------------------------

        await asyncio.to_thread(
            send_bot_notification,
            target_type,
            amount,
            text,
            message_time,
        )

    except Exception as e:

        print(
            f"❌ Message handler error: "
            f"{type(e).__name__}: {e}",
            flush=True,
        )


# ============================================================
# TELEGRAM WATCHER
# ============================================================

async def telegram_watcher():

    while True:

        try:

            print(
                "Connecting to Telegram...",
                flush=True,
            )

            # ------------------------------------------------
            # Connect using StringSession
            # ------------------------------------------------

            await client.connect()

            print(
                "Telegram transport connected.",
                flush=True,
            )

            # ------------------------------------------------
            # Check authorization
            # ------------------------------------------------

            authorized = await client.is_user_authorized()

            print(
                f"Telegram authorized: {authorized}",
                flush=True,
            )

            if not authorized:

                print(
                    "❌ ERROR: TELEGRAM_SESSION "
                    "is not authorized or is invalid.",
                    flush=True,
                )

                await client.disconnect()

                return

            # ------------------------------------------------
            # Logged-in Telegram account
            # ------------------------------------------------

            me = await client.get_me()

            username = (
                f"@{me.username}"
                if me.username
                else "No username"
            )

            print(
                f"✅ Logged in as: "
                f"{me.first_name} "
                f"({username})",
                flush=True,
            )

            # ------------------------------------------------
            # Find target group
            # ------------------------------------------------

            entity = await client.get_entity(
                TARGET_GROUP
            )

            print(
                f"✅ Group found: "
                f"{getattr(entity, 'title', TARGET_GROUP)}",
                flush=True,
            )

            print(
                f"Watching group: {TARGET_GROUP}",
                flush=True,
            )

            # ------------------------------------------------
            # Configuration
            # ------------------------------------------------

            print(
                "Monitoring time: "
                "07:00 - 12:00 IST",
                flush=True,
            )

            print(
                "Target types: "
                "PARITY | SAPRE | BCONE | EMERD",
                flush=True,
            )

            print(
                "Allowed amounts:",
                flush=True,
            )

            print(
                "90, 270, 810, 2430, 7290, "
                "900, 2700, 8100, 24300, 72900, "
                "9000, 27000, 81000, 243000, 729000",
                flush=True,
            )

            print(
                "Notifications: YOU + FRIEND",
                flush=True,
            )

            print(
                "👀 Waiting for new messages...",
                flush=True,
            )

            # ------------------------------------------------
            # Keep listening
            # ------------------------------------------------

            await client.run_until_disconnected()

            print(
                "⚠️ Telegram disconnected.",
                flush=True,
            )

        except Exception as e:

            print(
                f"❌ Telegram error: "
                f"{type(e).__name__}: {e}",
                flush=True,
            )

            try:
                await client.disconnect()

            except Exception:
                pass

            print(
                "🔄 Reconnecting in 10 seconds...",
                flush=True,
            )

            await asyncio.sleep(10)


# ============================================================
# MAIN
# ============================================================

async def main():

    # Start Flask health server
    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True,
    )

    flask_thread.start()

    # Start Telegram watcher
    await telegram_watcher()


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print(
            "Application stopped.",
            flush=True,
        )
