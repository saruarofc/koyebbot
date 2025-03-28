import requests
import os
import time
from pyrogram import Client, filters
from pyrogram.types import Message
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# RapidAPI details
RAPIDAPI_URL = "https://terabox-downloader-online-viewer-player-api.p.rapidapi.com/rapidapi"
RAPIDAPI_KEY = "40f2e82091mshde814f0686f92ffp1833b5jsn9c8efed709fb"
RAPIDAPI_HOST = "terabox-downloader-online-viewer-player-api.p.rapidapi.com"

# Initialize bot
app = Client("terabox_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Function to get download link
def get_download_link(terabox_url):
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }
    querystring = {"url": terabox_url}

    try:
        response = requests.get(RAPIDAPI_URL, headers=headers, params=querystring)
        data = response.json()
        return data.get("download_link")  # Extracting direct download link
    except Exception as e:
        print(f"Error fetching download link: {e}")
        return None

# Command handler for /start
@app.on_message(filters.command("start") & filters.private)
async def start(client, message: Message):
    await message.reply_text("👋 Welcome! Send me a Terabox link, and I'll fetch the video for you.")

# Handler for Terabox links
@app.on_message(filters.regex(r'https?://teraboxapp\.com/s/\S+') & filters.private)
async def fetch_video(client, message: Message):
    user_link = message.text.strip()
    msg = await message.reply_text("🔍 Fetching the download link...")

    download_url = get_download_link(user_link)
    if not download_url:
        await msg.edit("❌ Failed to fetch the download link. Please check the link and try again.")
        return

    await msg.edit("📥 Downloading the video...")

    video_path = f"downloaded_{int(time.time())}.mp4"
    try:
        video_response = requests.get(download_url, stream=True)
        with open(video_path, "wb") as f:
            for chunk in video_response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

        await msg.edit("✅ Download complete! Uploading now...")

        # Send video
        await client.send_video(message.chat.id, video_path, caption="🎬 Here is your downloaded video!")

        # Cleanup
        os.remove(video_path)

    except Exception as e:
        await msg.edit(f"❌ Error downloading video: {e}")

# Run the bot
if __name__ == "__main__":
    app.run()
