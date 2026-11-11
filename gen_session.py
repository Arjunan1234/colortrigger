from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = 2977839
api_hash = 'f9f63f6172789ca3ceb65932f51b28bd'

client = TelegramClient(StringSession(), api_id, api_hash)
client.start()

print("\n✅ SESSION STRING (copy this):")
print(client.session.save())

client.disconnect()
