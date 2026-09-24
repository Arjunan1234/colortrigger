import os
import re
import asyncio
import threading
from datetime import time
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

# Your Telegram chat ID
BOT_CHAT_ID = os.environ["BOT_CHAT_ID"]

# Esakki's Telegram chat ID
FRIEND_CHAT_ID = os.environ["FRIEND_CHAT_ID"]


# ============================================================
# TELEGRAM NOTIFICATION RECIPIENTS
# ============================================================

BOT_CHAT_IDS = [
    BOT_CHAT_ID,
    FRIEND_CHAT_ID,
]


# ============================================================
# TARGET GROUP
# ============================================================

TARGET_GROUP = "@colorwizclub2"


# ============================================================
# TARGET TYPES
# ============================================================

TARGET_TYPES = {
    "PARITY",
    "SAPRE",
    "BCONE",
    "EMERD",
}


# ============================================================
# EXACT AMOUNTS
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
# TIMEZONE / MONITORING WINDOW
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
# CHECK MONITORING TIME
# ============================================================

def is_allowed_time(message_time):

    current_time = message_time.time()

    return START_TIME <= current_time < END_TIME


# ============================================================
# EXTRACT TYPE + AMOUNT
#
# Handles messages like:
#
# **SAPRE 🔴 100**
# **SAPRE 🟢 300**
# **SAPRE 🟢 900**
# **EMERD 🔴 8100**
# **BCONE 🟢 24300**
# **PARITY 🔴 729000**
#
# Emoji does not matter.
# Markdown ** does not matter.
# ============================================================

def extract_target_content(text):

    if not text:
        return None

    # Normalize whitespace/newlines
    normalized_text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    # --------------------------------------------------------
    # Find target type
    # --------------------------------------------------------

    type_match = re.search(
        r"\b(PARITY|SAPRE|BCONE|EMERD)\b",
        normalized_text,
        re.IGNORECASE
    )

    if not type_match:
        return None

    content_type = type_match.group(1).upper()

    # --------------------------------------------------------
    # Everything after target type
    # --------------------------------------------------------

    text_after_keyword = normalized_text[
        type_match.end():
    ]

    # --------------------------------------------------------
    # Find first whole number after type
    #
    # Examples:
    # SAPRE 🔴 900
    # SAPRE 🟢 2430
    # --------------------------------------------------------

    amount_match = re.search(
        r"\b(\d+)\b",
        text_after_keyword
    )

    if not amount_match:
        return None

    try:
        amount = int(amount_match.group(1))

    except ValueError:
        return None

    return {
        "type": content_type,
        "amount": amount,
        "raw_text": normalized_text,
    }


# ============================================================
# SEND NOTIFICATION TO BOTH USERS
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
        f"{message_text}"
    )

    # --------------------------------------------------------
    # Send to YOU + ESAKKI
    # --------------------------------------------------------

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
                    f"✅ Alert sent to {chat_id} | "
                    f"{target_type} {amount}",
                    flush=True,
                )

            else:

                print(
                    f"❌ Telegram Bot API error | "
                    f"Chat: {chat_id} | "
                    f"Status: {response.status_code} | "
                    f"{response.text}",
                    flush=True,
                )

        except Exception as error:

            print(
                f"❌ Notification error | "
                f"Chat: {chat_id} | "
                f"{error}",
                flush=True,
            )


# ============================================================
# NEW TELEGRAM MESSAGE
# ============================================================

@client.on(events.NewMessage(chats=TARGET_GROUP))
async def new_message_handler(event):

    try:

        # ----------------------------------------------------
        # Convert Telegram timestamp to IST
        # ----------------------------------------------------

        message_time = event.message.date.astimezone(IST)

        # ----------------------------------------------------
        # ONLY 07:00 AM - 12:00 PM IST
        # ----------------------------------------------------

        if not is_allowed_time(message_time):

            return

        # ----------------------------------------------------
        # Get text
        # ----------------------------------------------------

        text = event.raw_text

        if not text:

            return

        # ----------------------------------------------------
        # Extract type + amount
        # ----------------------------------------------------

        extracted = extract_target_content(text)

        if not extracted:

            return

        target_type = extracted["type"]
        amount = extracted["amount"]

        # ----------------------------------------------------
        # Exact amount check
        # ----------------------------------------------------

        if amount not in ALLOWED_AMOUNTS:

            return

        # ====================================================
        # MATCH FOUND
        # ====================================================

        print(
            "\n========================================",
            flush=True,
        )

        print(
            "🚨 MATCH FOUND",
            flush=True,
        )

        print(
            f"Type   : {target_type}",
            flush=True,
        )

        print(
            f"Amount : {amount}",
            flush=True,
        )

        print(
            f"Time   : "
            f"{message_time.strftime('%Y-%m-%d %H:%M:%S')} IST",
            flush=True,
        )

        print(
            f"Message: {text}",
            flush=True,
        )

        print(
            "========================================",
            flush=True,
        )

        # ----------------------------------------------------
        # Send notification to both users
        # ----------------------------------------------------

        await asyncio.to_thread(
            send_bot_notification,
            target_type,
            amount,
            text,
            message_time,
        )

    except Exception as error:

        print(
            f"❌ Message handler error: "
            f"{type(error).__name__}: {error}",
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
            # Get logged-in account
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
            # Find group
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
                "Monitoring time: 07:00 - 12:00 IST",
                flush=True,
            )

            print(
                "Target types: "
                "PARITY | SAPRE | BCONE | EMERD",
                flush=True,
            )

            print(
                "Exact allowed amounts:",
                flush=True,
            )

            print(
                "90, 270, 810, 2430, 7290, "
                "900, 2700, 8100, 24300, 72900, "
                "9000, 27000, 81000, 243000, 729000",
                flush=True,
            )

            print(
                "Notifications: YOU + ESAKKI",
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

        except Exception as error:

            print(
                f"❌ Telegram error: "
                f"{type(error).__name__}: {error}",
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

    # --------------------------------------------------------
    # Start Flask health server
    # --------------------------------------------------------

    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True,
    )

    flask_thread.start()

    # --------------------------------------------------------
    # Start Telegram watcher
    # --------------------------------------------------------

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
