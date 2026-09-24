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

BOT_CHAT_ID = os.environ["BOT_CHAT_ID"]
FRIEND_CHAT_ID = os.environ["FRIEND_CHAT_ID"]


# ============================================================
# NOTIFICATION RECIPIENTS
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
# EXACT ALLOWED AMOUNTS
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
# TIMEZONE
# ============================================================

IST = ZoneInfo("Asia/Kolkata")

START_TIME = time(7, 0, 0)
END_TIME = time(12, 0, 0)


# ============================================================
# FLASK
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
# MESSAGE PARSER
# ============================================================

def extract_target_content(text):

    if not text:
        return None

    normalized_text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    # --------------------------------------------------------
    # Find type
    # --------------------------------------------------------

    type_match = re.search(
        r"\b(PARITY|SAPRE|BCONE|EMERD)\b",
        normalized_text,
        re.IGNORECASE,
    )

    if not type_match:
        return None

    content_type = type_match.group(1).upper()

    # --------------------------------------------------------
    # Get everything after type
    # --------------------------------------------------------

    text_after_type = normalized_text[
        type_match.end():
    ]

    # --------------------------------------------------------
    # Find number
    #
    # Supports:
    #
    # SAPRE 🔴 900
    # SAPRE 🟢 2430
    # **SAPRE 🟢 8100**
    # --------------------------------------------------------

    amount_match = re.search(
        r"\b(\d+)\b",
        text_after_type,
    )

    if not amount_match:
        return None

    amount = int(amount_match.group(1))

    return {
        "type": content_type,
        "amount": amount,
        "raw_text": normalized_text,
    }


# ============================================================
# SEND BOT MESSAGE
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

    for chat_id in BOT_CHAT_IDS:

        try:

            response = requests.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": notification,
                },
                timeout=15,
            )

            if response.ok:

                print(
                    f"✅ ALERT SENT → {chat_id}",
                    flush=True,
                )

            else:

                print(
                    f"❌ BOT ERROR → {chat_id}",
                    flush=True,
                )

                print(
                    response.text,
                    flush=True,
                )

        except Exception as error:

            print(
                f"❌ SEND ERROR → {chat_id}: {error}",
                flush=True,
            )


# ============================================================
# PROCESS MESSAGE
# ============================================================

async def process_message(event):

    try:

        # ----------------------------------------------------
        # Telegram message time → IST
        # ----------------------------------------------------

        message_time = event.message.date.astimezone(IST)

        # ----------------------------------------------------
        # Ignore outside monitoring time
        # ----------------------------------------------------

        if not (
            START_TIME
            <= message_time.time()
            < END_TIME
        ):

            return

        # ----------------------------------------------------
        # Text
        # ----------------------------------------------------

        text = event.raw_text

        if not text:

            return

        # ----------------------------------------------------
        # IMPORTANT DEBUG
        #
        # This proves whether Render receives messages.
        # ----------------------------------------------------

        print(
            "\n📩 NEW GROUP MESSAGE",
            flush=True,
        )

        print(
            f"Time: "
            f"{message_time.strftime('%H:%M:%S')} IST",
            flush=True,
        )

        print(
            f"Text: {text}",
            flush=True,
        )

        # ----------------------------------------------------
        # Extract target
        # ----------------------------------------------------

        result = extract_target_content(text)

        if not result:

            print(
                "Not a target message.",
                flush=True,
            )

            return

        target_type = result["type"]
        amount = result["amount"]

        print(
            f"Detected type: {target_type}",
            flush=True,
        )

        print(
            f"Detected amount: {amount}",
            flush=True,
        )

        # ----------------------------------------------------
        # Exact amount check
        # ----------------------------------------------------

        if amount not in ALLOWED_AMOUNTS:

            print(
                f"Amount {amount} is NOT in allowed list.",
                flush=True,
            )

            return

        # ====================================================
        # MATCH
        # ====================================================

        print(
            "\n🚨🚨🚨 MATCH FOUND 🚨🚨🚨",
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
            f"{message_time.strftime('%H:%M:%S')} IST",
            flush=True,
        )

        print(
            f"Message: {text}",
            flush=True,
        )

        # ----------------------------------------------------
        # Send notification
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
            f"❌ PROCESS MESSAGE ERROR: "
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

            await client.connect()

            print(
                "Telegram transport connected.",
                flush=True,
            )

            authorized = (
                await client.is_user_authorized()
            )

            print(
                f"Telegram authorized: {authorized}",
                flush=True,
            )

            if not authorized:

                print(
                    "❌ TELEGRAM SESSION IS NOT AUTHORIZED",
                    flush=True,
                )

                await client.disconnect()

                return

            # ------------------------------------------------
            # Logged-in account
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
            # Resolve group
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
                f"Group ID: {entity.id}",
                flush=True,
            )

            print(
                f"Watching group: {TARGET_GROUP}",
                flush=True,
            )

            # =================================================
            # REGISTER HANDLER USING RESOLVED ENTITY
            # =================================================

            client.add_event_handler(
                process_message,
                events.NewMessage(chats=entity),
            )

            print(
                "✅ Message listener registered.",
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
                "👀 Waiting for NEW messages...",
                flush=True,
            )

            # ------------------------------------------------
            # Keep connection alive
            # ------------------------------------------------

            await client.run_until_disconnected()

            print(
                "⚠️ Telegram disconnected.",
                flush=True,
            )

        except Exception as error:

            print(
                f"❌ TELEGRAM ERROR: "
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

    # Start health server
    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True,
    )

    flask_thread.start()

    # Start Telegram
    await telegram_watcher()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print(
            "Application stopped.",
            flush=True,
        )
