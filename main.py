import os
import re
import asyncio
import threading
import unicodedata

from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from flask import Flask
from telethon import TelegramClient, events, utils
from telethon.sessions import StringSession


# =========================================================
# LOAD ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION_STRING = os.environ["TELEGRAM_SESSION"]

BOT_TOKEN = os.environ["BOT_TOKEN"]
BOT_CHAT_ID = os.environ["BOT_CHAT_ID"]
FRIEND_CHAT_ID = os.environ["FRIEND_CHAT_ID"]


# =========================================================
# CONFIGURATION
# =========================================================

BOT_CHAT_IDS = [
    BOT_CHAT_ID,
    FRIEND_CHAT_ID,
]

TARGET_GROUP = "@colorwizclub2"

TARGET_TYPES = {
    "PARITY",
    "SAPRE",
    "BCONE",
    "EMERD",
}


# =========================================================
# EXACT ALLOWED AMOUNTS
# =========================================================

ALLOWED_AMOUNTS = {
    # Group 1
    90,
    270,
    810,
    2430,
    7290,

    # Group 2
    900,
    2700,
    8100,
    24300,
    72900,

    # Group 3
    9000,
    27000,
    81000,
    243000,
    729000,
}


IST = ZoneInfo("Asia/Kolkata")


# =========================================================
# FLASK HEALTH SERVER
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "ColorTrigger is running", 200


@app.route("/health")
def health():
    return "OK", 200


def start_health_server():
    """
    Start Flask in a background thread.
    Render uses this HTTP server to keep the web service alive.
    """

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True,
        use_reloader=False,
    )


# =========================================================
# TELEGRAM CLIENT
# =========================================================

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH,
)


TARGET_ENTITY = None
TARGET_ENTITY_ID = None


# =========================================================
# EMOJI EXTRACTOR
# =========================================================

def extract_emoji(text):
    """
    Extract emoji/symbol characters from the text between
    the message type and the amount.

    Example:

        " 🔴 " -> "🔴"
        " 🟢 " -> "🟢"

    This also supports other Unicode emoji/symbols.
    """

    if not text:
        return ""

    result = []

    for char in text:
        code = ord(char)
        category = unicodedata.category(char)

        # Unicode symbol categories
        if category.startswith("So") or category.startswith("Sk"):
            result.append(char)

        # Emoji variation selector
        elif code in range(0xFE00, 0xFE10):
            result.append(char)

        # Zero-width joiner
        elif code == 0x200D:
            result.append(char)

    return "".join(result).strip()


# =========================================================
# PARSER
# =========================================================

def parse_message(text):
    """
    Detect:

        PARITY 90
        PARITY 🟢 900
        SAPRE 🔴 900
        BCONE 🟢 8100
        EMERD 🔴 72900

    The amount must be one of the exact allowed amounts.

    Returns:

        {
            "type": "PARITY",
            "emoji": "🟢",
            "amount": 900
        }

    or None if it doesn't match.
    """

    if not text:
        return None

    # Normalize whitespace
    normalized = re.sub(r"\s+", " ", text).strip()

    # Find one of the supported types
    type_match = re.search(
        r"\b(PARITY|SAPRE|BCONE|EMERD)\b",
        normalized,
        re.IGNORECASE,
    )

    if not type_match:
        return None

    message_type = type_match.group(1).upper()

    # Only search for the amount AFTER the detected type
    remaining_text = normalized[type_match.end():]

    # Find the first number after the type
    amount_match = re.search(
        r"\b(\d+)\b",
        remaining_text,
    )

    if not amount_match:
        return None

    amount = int(amount_match.group(1))

    # Exact amount check
    if amount not in ALLOWED_AMOUNTS:
        return None

    # Everything between TYPE and AMOUNT
    between_type_and_amount = remaining_text[
        :amount_match.start()
    ]

    # Extract emoji
    emoji = extract_emoji(
        between_type_and_amount
    )

    return {
        "type": message_type,
        "emoji": emoji,
        "amount": amount,
    }


# =========================================================
# SEND TELEGRAM BOT MESSAGE
# =========================================================

def send_bot_message(message):
    """
    Send notification to both configured Telegram chat IDs.
    """

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    for chat_id in BOT_CHAT_IDS:

        try:

            response = requests.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": message,
                },
                timeout=15,
            )

            if response.ok:

                print(
                    f"✅ Bot notification sent → {chat_id}",
                    flush=True,
                )

            else:

                print(
                    f"❌ Bot notification failed → {chat_id}",
                    flush=True,
                )

                print(
                    f"HTTP {response.status_code}: "
                    f"{response.text}",
                    flush=True,
                )

        except Exception as error:

            print(
                f"❌ Bot request error → {chat_id}: {error}",
                flush=True,
            )


# =========================================================
# PROCESS NEW TELEGRAM MESSAGE
# =========================================================

async def process_message(event):

    try:

        chat_id = event.chat_id

        message = event.message

        text = message.raw_text or ""

        print("\n" + "=" * 60, flush=True)
        print("📩 NEW TELEGRAM MESSAGE", flush=True)
        print(f"Chat ID : {chat_id}", flush=True)
        print(f"Text    : {text}", flush=True)
        print("=" * 60, flush=True)


        # -------------------------------------------------
        # TARGET GROUP CHECK
        # -------------------------------------------------

        if TARGET_ENTITY_ID is None:

            print(
                "⚠️ TARGET_ENTITY_ID is not initialized yet.",
                flush=True,
            )

            return


        if chat_id != TARGET_ENTITY_ID:

            print(
                "↪️ Ignored: message is from another chat.",
                flush=True,
            )

            return


        # -------------------------------------------------
        # TARGET GROUP MESSAGE
        # -------------------------------------------------

        message_time = message.date

        if message_time:

            message_time_ist = message_time.astimezone(IST)

            formatted_time = message_time_ist.strftime(
                "%Y-%m-%d %I:%M:%S %p"
            )

        else:

            formatted_time = "Unknown time"


        print(
            "\n🎯 TARGET GROUP MESSAGE",
            flush=True,
        )

        print(
            f"Time : {formatted_time}",
            flush=True,
        )

        print(
            f"Text : {text}",
            flush=True,
        )


        # -------------------------------------------------
        # PARSE MESSAGE
        # -------------------------------------------------

        parsed = parse_message(text)

        if not parsed:

            print(
                "❌ No valid target type + allowed amount found.",
                flush=True,
            )

            return


        message_type = parsed["type"]
        emoji = parsed["emoji"]
        amount = parsed["amount"]


        # -------------------------------------------------
        # MATCH FOUND
        # -------------------------------------------------

        print(
            "\n🚨 MATCH FOUND",
            flush=True,
        )

        print(
            f"Type   : {message_type}",
            flush=True,
        )

        print(
            f"Emoji  : {emoji if emoji else 'None'}",
            flush=True,
        )

        print(
            f"Amount : {amount}",
            flush=True,
        )


        # -------------------------------------------------
        # CREATE DISPLAY MESSAGE
        # -------------------------------------------------

        if emoji:

            trigger_text = (
                f"{message_type} "
                f"{emoji} "
                f"{amount}"
            )

        else:

            trigger_text = (
                f"{message_type} "
                f"{amount}"
            )


        print(
            f"Trigger: {trigger_text}",
            flush=True,
        )


        # -------------------------------------------------
        # NOTIFICATION
        # -------------------------------------------------

        notification = (
            "🚨 COLOR TRIGGER\n\n"
            f"{trigger_text}\n\n"
            f"Time: {formatted_time}\n"
            f"Group: {TARGET_GROUP}"
        )


        await asyncio.to_thread(
            send_bot_message,
            notification,
        )


    except Exception as error:

        print(
            f"❌ Error processing message: {error}",
            flush=True,
        )


# =========================================================
# TEST LATEST GROUP MESSAGE
# =========================================================

async def test_latest_message(entity):

    try:

        print(
            "\n🔎 Checking latest message from target group...",
            flush=True,
        )

        messages = await client.get_messages(
            entity,
            limit=1,
        )

        if not messages:

            print(
                "⚠️ No messages found.",
                flush=True,
            )

            return


        latest = messages[0]

        latest_text = latest.raw_text or ""

        latest_time = latest.date

        if latest_time:

            latest_time_ist = latest_time.astimezone(IST)

            latest_time_string = latest_time_ist.strftime(
                "%Y-%m-%d %I:%M:%S %p"
            )

        else:

            latest_time_string = "Unknown"


        print(
            "\n📌 LATEST GROUP MESSAGE",
            flush=True,
        )

        print(
            f"Message ID : {latest.id}",
            flush=True,
        )

        print(
            f"Time       : {latest_time_string}",
            flush=True,
        )

        print(
            f"Text       : {latest_text}",
            flush=True,
        )


    except Exception as error:

        print(
            f"⚠️ Latest-message test failed: {error}",
            flush=True,
        )


# =========================================================
# TELEGRAM WATCHER
# =========================================================

async def telegram_watcher():

    global TARGET_ENTITY
    global TARGET_ENTITY_ID


    while True:

        try:

            # -------------------------------------------------
            # CONNECT
            # -------------------------------------------------

            if not client.is_connected():

                print(
                    "🔌 Connecting to Telegram...",
                    flush=True,
                )

                await client.connect()

                print(
                    "Telegram transport connected.",
                    flush=True,
                )


            # -------------------------------------------------
            # AUTHORIZATION CHECK
            # -------------------------------------------------

            authorized = await client.is_user_authorized()

            print(
                f"Telegram authorized: {authorized}",
                flush=True,
            )


            if not authorized:

                print(
                    "\n❌ Telegram session is NOT authorized.",
                    flush=True,
                )

                print(
                    "Check TELEGRAM_SESSION in Render.",
                    flush=True,
                )

                await asyncio.sleep(30)

                continue


            # -------------------------------------------------
            # GET ACCOUNT
            # -------------------------------------------------

            me = await client.get_me()

            username = (
                f"@{me.username}"
                if me.username
                else "No username"
            )


            print(
                f"✅ Logged in as: "
                f"{me.first_name or ''} "
                f"({username})",
                flush=True,
            )


            # -------------------------------------------------
            # FIND TARGET GROUP
            # -------------------------------------------------

            print(
                f"🔎 Resolving group: {TARGET_GROUP}",
                flush=True,
            )


            TARGET_ENTITY = await client.get_entity(
                TARGET_GROUP
            )


            # -------------------------------------------------
            # IMPORTANT PEER ID FIX
            # -------------------------------------------------

            TARGET_ENTITY_ID = utils.get_peer_id(
                TARGET_ENTITY
            )


            print(
                "\n✅ Group found:",
                getattr(
                    TARGET_ENTITY,
                    "title",
                    TARGET_GROUP,
                ),
                flush=True,
            )


            print(
                f"Entity ID: "
                f"{getattr(TARGET_ENTITY, 'id', 'unknown')}",
                flush=True,
            )


            print(
                f"Peer ID: {TARGET_ENTITY_ID}",
                flush=True,
            )


            print(
                f"Watching group: {TARGET_GROUP}",
                flush=True,
            )


            # -------------------------------------------------
            # TEST GROUP ACCESS
            # -------------------------------------------------

            await test_latest_message(
                TARGET_ENTITY
            )


            # -------------------------------------------------
            # REMOVE OLD HANDLER
            # -------------------------------------------------

            try:

                client.remove_event_handler(
                    process_message,
                    events.NewMessage,
                )

            except Exception:

                pass


            # -------------------------------------------------
            # REGISTER NEW MESSAGE HANDLER
            # -------------------------------------------------

            client.add_event_handler(
                process_message,
                events.NewMessage(),
            )


            print(
                "\n✅ Message listener registered.",
                flush=True,
            )


            print(
                "⏰ Monitoring: 24 HOURS / 7 DAYS",
                flush=True,
            )


            print(
                f"🎯 Target peer ID: {TARGET_ENTITY_ID}",
                flush=True,
            )


            print(
                "\n👀 Waiting for NEW messages 24/7...",
                flush=True,
            )


            print(
                "Pressing nothing is required. "
                "The listener stays active.",
                flush=True,
            )


            # -------------------------------------------------
            # WAIT FOREVER
            # -------------------------------------------------

            await client.run_until_disconnected()


            print(
                "\n⚠️ Telegram disconnected.",
                flush=True,
            )


            print(
                "Reconnecting in 10 seconds...",
                flush=True,
            )


            await asyncio.sleep(10)


        except Exception as error:

            print(
                "\n❌ TELEGRAM WATCHER ERROR",
                flush=True,
            )

            print(
                repr(error),
                flush=True,
            )


            print(
                "\n🔄 Retrying in 10 seconds...",
                flush=True,
            )


            await asyncio.sleep(10)


# =========================================================
# MAIN
# =========================================================

async def main():

    print(
        "\n" + "=" * 60,
        flush=True,
    )

    print(
        "🚀 COLORTRIGGER STARTING",
        flush=True,
    )

    print(
        "=" * 60,
        flush=True,
    )


    # -------------------------------------------------
    # START FLASK HEALTH SERVER
    # -------------------------------------------------

    health_thread = threading.Thread(
        target=start_health_server,
        daemon=True,
    )

    health_thread.start()


    print(
        "🌐 Health server started.",
        flush=True,
    )


    # -------------------------------------------------
    # START TELEGRAM WATCHER
    # -------------------------------------------------

    await telegram_watcher()


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print(
            "\n🛑 Application stopped.",
            flush=True,
        )

    except Exception as error:

        print(
            f"\n❌ Application crashed: {error}",
            flush=True,
        )
