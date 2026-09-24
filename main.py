import os
import re
import asyncio
import threading
from datetime import datetime, timezone, timedelta, time

import requests
from flask import Flask, jsonify
from telethon import TelegramClient, events
from telethon.sessions import StringSession


# ============================================================
# CONFIG
# ============================================================

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]

# Telethon StringSession for your Telegram USER account
SESSION_STRING = os.environ["TELEGRAM_SESSION"]

# Telegram notification bot
BOT_TOKEN = os.environ["BOT_TOKEN"]
BOT_CHAT_ID = os.environ["BOT_CHAT_ID"]

# Telegram group/channel
TARGET_GROUP = "@colorwizclub2"

# IST
IST = timezone(timedelta(hours=5, minutes=30))

# Alert types
TARGET_TYPES = {
    "PARITY",
    "SAPRE",
    "BCONE",
    "EMERD",
}

# Minimum amount
MIN_AMOUNT = 900


# ============================================================
# FLASK SERVER
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Telegram watcher is running."


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "telegram-900-watcher"
    })


# ============================================================
# TIME CHECK
# ============================================================

def is_alert_time():
    now = datetime.now(IST)
    current_time = now.time()

    start_time = time(7, 0, 0)
    end_time = time(12, 0, 0)

    return start_time <= current_time < end_time


# ============================================================
# EXTRACT TYPE + AMOUNT
# ============================================================

def extract_target_content(text):

    if not text:
        return None

    # Normalize spaces/newlines
    normalized_text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    # Find target type
    type_match = re.search(
        r"\b(PARITY|SAPRE|BCONE|EMERD)\b",
        normalized_text,
        re.IGNORECASE
    )

    if not type_match:
        return None

    content_type = type_match.group(1).upper()

    # Everything after target type
    text_after_keyword = normalized_text[
        type_match.end():
    ]

    # Find first number after target type
    amount_match = re.search(
        r"\b(\d+(?:\.\d+)?)\b",
        text_after_keyword
    )

    if not amount_match:
        return None

    amount_text = amount_match.group(1)

    if "." in amount_text:
        amount = float(amount_text)
    else:
        amount = int(amount_text)

    return {
        "type": content_type,
        "amount": amount,
        "text": normalized_text
    }


# ============================================================
# SEND TELEGRAM NOTIFICATION
# ============================================================

def send_notification(
    content_type,
    amount,
    message_time,
    original_text
):

    alert_text = (
        "🚨 900+ ALERT\n\n"
        f"Type: {content_type}\n"
        f"Amount: {amount}\n"
        f"Time: {message_time} IST\n\n"
        f"{original_text}"
    )

    url = (
        f"https://api.telegram.org/bot"
        f"{BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": BOT_CHAT_ID,
        "text": alert_text
    }

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=15
        )

        if response.ok:

            print(
                f"[ALERT SENT] "
                f"{content_type} | "
                f"{amount} | "
                f"{message_time}"
            )

        else:

            print(
                "[BOT ERROR]",
                response.status_code,
                response.text
            )

    except Exception as error:

        print(
            "[NOTIFICATION ERROR]",
            error
        )


# ============================================================
# TELEGRAM CLIENT
# ============================================================

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH
)


# ============================================================
# NEW MESSAGE HANDLER
# ============================================================

@client.on(events.NewMessage(chats=TARGET_GROUP))
async def new_message_handler(event):

    try:

        # Current IST time
        now = datetime.now(IST)

        # Only monitor 07:00 - 12:00 IST
        if not is_alert_time():

            return

        # Only text/caption
        text = event.raw_text

        if not text:

            return

        # Extract target + amount
        extracted = extract_target_content(text)

        if not extracted:

            return

        content_type = extracted["type"]
        amount = extracted["amount"]
        original_text = extracted["text"]

        # Only 900+
        if amount < MIN_AMOUNT:

            return

        # Message timestamp
        message_date = event.message.date

        if message_date.tzinfo is None:

            message_date = message_date.replace(
                tzinfo=timezone.utc
            )

        message_ist = message_date.astimezone(IST)

        message_time = message_ist.strftime(
            "%H:%M:%S"
        )

        print(
            "\n========================================"
        )

        print(
            "🚨 MATCH FOUND"
        )

        print(
            f"Type   : {content_type}"
        )

        print(
            f"Amount : {amount}"
        )

        print(
            f"Time   : {message_time}"
        )

        print(
            f"Text   : {original_text}"
        )

        print(
            "========================================\n"
        )

        # Send Telegram notification
        await asyncio.to_thread(
            send_notification,
            content_type,
            amount,
            message_time,
            original_text
        )

    except Exception as error:

        print(
            "[MESSAGE HANDLER ERROR]",
            error
        )


# ============================================================
# TELEGRAM WATCHER
# ============================================================

async def telegram_watcher():

    while True:

        try:

            print(
                "\nConnecting to Telegram..."
            )

            await client.start()

            print(
                "Telegram connected."
            )

            me = await client.get_me()

            if me:

                username = (
                    f"@{me.username}"
                    if me.username
                    else ""
                )

                print(
                    f"Logged in as: "
                    f"{me.first_name or ''} "
                    f"{username}"
                )

            # Make sure group is accessible
            entity = await client.get_entity(
                TARGET_GROUP
            )

            print(
                f"Watching group: "
                f"{getattr(entity, 'title', TARGET_GROUP)}"
            )

            print(
                "Monitoring: 07:00 - 12:00 IST"
            )

            print(
                "Minimum amount: 900"
            )

            print(
                "Types: PARITY | SAPRE | BCONE | EMERD"
            )

            print(
                "\n👀 Waiting for new messages...\n"
            )

            # Stay connected
            await client.run_until_disconnected()

        except Exception as error:

            print(
                "\nTelegram connection error:",
                error
            )

            print(
                "Reconnecting in 10 seconds..."
            )

            try:
                await client.disconnect()
            except Exception:
                pass

            await asyncio.sleep(10)


# ============================================================
# RUN FLASK
# ============================================================

def run_flask():

    port = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    # Flask runs in background thread
    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True
    )

    flask_thread.start()

    # Telegram watcher
    await telegram_watcher()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print(
            "\nWatcher stopped."
        )
