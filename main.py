import os
import re
import asyncio
import threading
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

import requests
from flask import Flask
from telethon import TelegramClient, events, utils
from telethon.sessions import StringSession


# ============================================================
# LOAD .ENV
# ============================================================

load_dotenv()


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
# TARGET TELEGRAM GROUP
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


# ============================================================
# FLASK HEALTH SERVER
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Telegram watcher is running 24/7."


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
# TARGET GROUP INFORMATION
# ============================================================

TARGET_ENTITY = None
TARGET_ENTITY_ID = None


# ============================================================
# MESSAGE PARSER
# ============================================================

def extract_target_content(text):

    if not text:
        return None

    # --------------------------------------------------------
    # Normalize whitespace
    # --------------------------------------------------------

    normalized_text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    # --------------------------------------------------------
    # Find target type
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
    # Get everything after target type
    # --------------------------------------------------------

    text_after_type = normalized_text[
        type_match.end():
    ]

    # --------------------------------------------------------
    # Find amount
    #
    # Examples:
    #
    # SAPRE 🔴 900
    # SAPRE 🟢 2430
    # **SAPRE 🟢 8100**
    # EMERD 729000
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
# SEND BOT NOTIFICATION
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
        f"Time: "
        f"{message_time.strftime('%Y-%m-%d %H:%M:%S')} IST\n\n"
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
                    f"Status: {response.status_code}",
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
# PROCESS NEW TELEGRAM MESSAGE
# ============================================================

async def process_message(event):

    try:

        # ----------------------------------------------------
        # Get incoming chat ID
        # ----------------------------------------------------

        chat_id = event.chat_id

        # ----------------------------------------------------
        # Debug every incoming Telegram message
        # ----------------------------------------------------

        print(
            "\n📩 NEW TELEGRAM MESSAGE",
            flush=True,
        )

        print(
            f"Incoming Chat ID : {chat_id}",
            flush=True,
        )

        print(
            f"Target Chat ID   : {TARGET_ENTITY_ID}",
            flush=True,
        )

        # ----------------------------------------------------
        # Check whether this is our target group
        # ----------------------------------------------------

        if chat_id != TARGET_ENTITY_ID:

            print(
                "↳ Not the target group. Ignored.",
                flush=True,
            )

            return

        # ----------------------------------------------------
        # Message time → IST
        # ----------------------------------------------------

        message_time = (
            event.message.date.astimezone(IST)
        )

        # ----------------------------------------------------
        # Message text
        # ----------------------------------------------------

        text = event.raw_text

        if not text:

            print(
                "↳ Target group message has no text.",
                flush=True,
            )

            return

        # ====================================================
        # TARGET GROUP MESSAGE
        # ====================================================

        print(
            "\n"
            "============================================",
            flush=True,
        )

        print(
            "🎯 TARGET GROUP MESSAGE RECEIVED",
            flush=True,
        )

        print(
            f"Chat ID : {chat_id}",
            flush=True,
        )

        print(
            "Time    : "
            f"{message_time.strftime('%Y-%m-%d %H:%M:%S')} IST",
            flush=True,
        )

        print(
            f"Text    : {text}",
            flush=True,
        )

        print(
            "============================================",
            flush=True,
        )

        # ----------------------------------------------------
        # Parse target
        # ----------------------------------------------------

        result = extract_target_content(text)

        if not result:

            print(
                "ℹ️ Not PARITY / SAPRE / BCONE / EMERD.",
                flush=True,
            )

            return

        target_type = result["type"]
        amount = result["amount"]

        print(
            f"Detected type   : {target_type}",
            flush=True,
        )

        print(
            f"Detected amount : {amount}",
            flush=True,
        )

        # ----------------------------------------------------
        # Exact amount check
        # ----------------------------------------------------

        if amount not in ALLOWED_AMOUNTS:

            print(
                f"❌ Amount {amount} is NOT allowed.",
                flush=True,
            )

            return

        # ====================================================
        # MATCH FOUND
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
            "Time   : "
            f"{message_time.strftime('%Y-%m-%d %H:%M:%S')} IST",
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
            "\n❌ PROCESS MESSAGE ERROR",
            flush=True,
        )

        print(
            f"Type : {type(error).__name__}",
            flush=True,
        )

        print(
            f"Error: {error}",
            flush=True,
        )


# ============================================================
# TEST GROUP ACCESS
# ============================================================

async def test_latest_message(entity):

    print(
        "\n"
        "============================================",
        flush=True,
    )

    print(
        "🔎 TESTING GROUP ACCESS",
        flush=True,
    )

    print(
        "Reading latest message...",
        flush=True,
    )

    try:

        messages = await client.get_messages(
            entity,
            limit=1,
        )

        if not messages:

            print(
                "⚠️ No messages returned from group.",
                flush=True,
            )

            return

        latest = messages[0]

        latest_time = None

        if latest.date:

            latest_time = (
                latest.date.astimezone(IST)
            )

        print(
            "✅ Successfully read latest group message.",
            flush=True,
        )

        print(
            f"Message ID : {latest.id}",
            flush=True,
        )

        if latest_time:

            print(
                "Time       : "
                f"{latest_time.strftime('%Y-%m-%d %H:%M:%S')} IST",
                flush=True,
            )

        print(
            f"Text       : {latest.raw_text}",
            flush=True,
        )

        print(
            "============================================",
            flush=True,
        )

    except Exception as error:

        print(
            "❌ FAILED TO READ LATEST GROUP MESSAGE",
            flush=True,
        )

        print(
            f"Type : {type(error).__name__}",
            flush=True,
        )

        print(
            f"Error: {error}",
            flush=True,
        )


# ============================================================
# TELEGRAM WATCHER
# ============================================================

async def telegram_watcher():

    global TARGET_ENTITY
    global TARGET_ENTITY_ID

    while True:

        try:

            print(
                "\n🔌 Connecting to Telegram...",
                flush=True,
            )

            # ------------------------------------------------
            # Connect
            # ------------------------------------------------

            if not client.is_connected():

                await client.connect()

            print(
                "✅ Telegram transport connected.",
                flush=True,
            )

            # ------------------------------------------------
            # Authorization
            # ------------------------------------------------

            authorized = (
                await client.is_user_authorized()
            )

            print(
                f"Telegram authorized: {authorized}",
                flush=True,
            )

            if not authorized:

                print(
                    "\n"
                    "❌ TELEGRAM SESSION IS NOT AUTHORIZED",
                    flush=True,
                )

                print(
                    "Please generate a new Telegram session.",
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
            # Resolve target group
            # ------------------------------------------------

            entity = await client.get_entity(
                TARGET_GROUP
            )

            TARGET_ENTITY = entity

            # IMPORTANT:
            # Convert Telegram entity ID to the same peer ID
            # format used by incoming events.

            TARGET_ENTITY_ID = utils.get_peer_id(
                entity
            )

            print(
                f"✅ Group found: "
                f"{getattr(entity, 'title', TARGET_GROUP)}",
                flush=True,
            )

            print(
                f"Entity ID: {entity.id}",
                flush=True,
            )

            print(
                f"Peer ID  : {TARGET_ENTITY_ID}",
                flush=True,
            )

            print(
                f"Watching group: {TARGET_GROUP}",
                flush=True,
            )

            # ------------------------------------------------
            # Test latest message
            # ------------------------------------------------

            await test_latest_message(entity)

            # =================================================
            # REMOVE OLD HANDLER
            # =================================================

            try:

                client.remove_event_handler(
                    process_message,
                    events.NewMessage,
                )

            except Exception:

                pass

            # =================================================
            # REGISTER GLOBAL NEW MESSAGE LISTENER
            # =================================================

            client.add_event_handler(
                process_message,
                events.NewMessage(),
            )

            print(
                "✅ Global Telegram message listener registered.",
                flush=True,
            )

            # =================================================
            # CONFIGURATION
            # =================================================

            print(
                "\n"
                "============================================",
                flush=True,
            )

            print(
                "🚀 WATCHER READY",
                flush=True,
            )

            print(
                "⏰ Monitoring: 24 HOURS / 7 DAYS",
                flush=True,
            )

            print(
                "🌐 Timezone: Asia/Kolkata (IST)",
                flush=True,
            )

            print(
                f"🎯 Target group: {TARGET_GROUP}",
                flush=True,
            )

            print(
                f"🎯 Entity ID: {entity.id}",
                flush=True,
            )

            print(
                f"🎯 Peer ID: {TARGET_ENTITY_ID}",
                flush=True,
            )

            print(
                "🎯 Target types: "
                "PARITY | SAPRE | BCONE | EMERD",
                flush=True,
            )

            print(
                "💰 Allowed amounts:",
                flush=True,
            )

            print(
                "90, 270, 810, 2430, 7290, "
                "900, 2700, 8100, 24300, 72900, "
                "9000, 27000, 81000, 243000, 729000",
                flush=True,
            )

            print(
                "🔔 Notifications: YOU + FRIEND",
                flush=True,
            )

            print(
                "👀 Waiting for NEW Telegram messages...",
                flush=True,
            )

            print(
                "============================================",
                flush=True,
            )

            # ------------------------------------------------
            # Keep connection alive
            # ------------------------------------------------

            await client.run_until_disconnected()

            print(
                "\n⚠️ Telegram disconnected.",
                flush=True,
            )

        except Exception as error:

            print(
                "\n❌ TELEGRAM WATCHER ERROR",
                flush=True,
            )

            print(
                f"Type : {type(error).__name__}",
                flush=True,
            )

            print(
                f"Error: {error}",
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

    print(
        "🌐 Health server started.",
        flush=True,
    )

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
            "\nApplication stopped.",
            flush=True,
        )
