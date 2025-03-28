import os import requests from pyrogram import Client, filters from pyrogram.types import Message

API_ID = int(os.getenv("API_ID")) API_HASH = os.getenv("API_HASH") BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client( "terabox_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN )

RAPIDAPI_HOST = "terabox-downloader-online-viewer-player-api.p.rapidapi.com" RAPIDAPI_KEY = "40f2e82091mshde814f0686f92ffp1833b5jsn9c8efed709fb" API_URL = "https://terabox-downloader-online-viewer-player-api.p.rapidapi.com/rapidapi"

@app.on_message(filters.command("start") & filters.private) def start(client, message: Message): message.reply_text(f"Hello {message.from_user.first_name}! 👋\nSend me a Terabox link, and I'll fetch the details for you.")

@app.on_message(filters.private & filters.text & filters.regex(r'https?://teraboxapp.com/s/\S+')) def fetch_terabox_details(client, message: Message): terabox_url = message.text.strip() headers = { "Accept": "application/json", "x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": RAPIDAPI_HOST, } params = {"url": terabox_url} try: response = requests.get(API_URL, headers=headers, params=params) response_data = response.json() if response.status_code == 200: message.reply_text(f"Here is the response from Terabox API:\n\n{response_data}") else: message.reply_text("Failed to fetch details. Please try again later.") except Exception as e: message.reply_text(f"Error occurred: {str(e)}")

if name == "main": app.run()

