import os import requests from pyrogram import Client, filters from pyrogram.types import Message from config import API_ID, API_HASH, BOT_TOKEN

Initialize the bot

class Bot(Client): def init(self): super().init( "terabox_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=10, sleep_threshold=10 )

async def start(self):
    await super().start()
    me = await self.get_me()
    self.username = '@' + me.username
    print(f'TeraBox Bot Started - {self.username}')

async def stop(self, *args):
    await super().stop()
    print('TeraBox Bot Stopped')

app = Bot()

API endpoint details

RAPIDAPI_HOST = "terabox-downloader-online-viewer-player-api.p.rapidapi.com" RAPIDAPI_KEY = "40f2e82091mshde814f0686f92ffp1833b5jsn9c8efed709fb" API_URL = "https://terabox-downloader-online-viewer-player-api.p.rapidapi.com/rapidapi"

/start command

@app.on_message(filters.command("start") & filters.private) async def start(client, message: Message): await message.reply_text(f"Hello {message.from_user.first_name}! 👋\nSend me a Terabox link, and I'll fetch the details for you.")

Handle Terabox links

@app.on_message(filters.private & filters.text & filters.regex(r'https?://teraboxapp.com/s/\S+')) async def fetch_terabox_details(client, message: Message): terabox_url = message.text.strip()

headers = {
    "Accept": "application/json",
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": RAPIDAPI_HOST,
}

params = {"url": terabox_url}

status_message = await message.reply_text("⏳ *Fetching details...*")

try:
    response = requests.get(API_URL, headers=headers, params=params)
    response_data = response.json()
    
    if response.status_code == 200:
        await status_message.edit_text(f"Here is the response from Terabox API:\n\n{response_data}")
    else:
        await status_message.edit_text("Failed to fetch details. Please try again later.")
except Exception as e:
    await status_message.edit_text(f"Error occurred: {str(e)}")

Run the bot

if name == "main": app.run()

