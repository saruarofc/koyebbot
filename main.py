from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
import os
import yt_dlp
import asyncio

from config import API_ID, API_HASH, BOT_TOKEN

# Initialize the bot
class Bot(Client):
    def init(self):
        super().init(
            "video_downloader_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=10,
            sleep_threshold=10
        )

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.username = '@' + me.username
        print(f'Video Downloader Bot Started - {self.username}')

    async def stop(self, *args):
        await super().stop()
        print('Video Downloader Bot Stopped')

# Create bot instance
app = Bot()

# Welcome message
@app.on_message(filters.command("start") & filters.private)
async def start(client, message: Message):
    welcome_text = (
        "🎥 *Welcome to Video Downloader Bot!* 🎥\n\n"
        "Send me a YouTube link, and I'll download and send the video to you!"
    )
    await message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

# Handle video links
@app.on_message(filters.text & filters.private)
async def download_video(client, message: Message):
    url = message.text.strip()

    # Validate URL
    if not url.startswith(("http://", "https://")):
        await message.reply_text("❌ Please send a valid video link!", parse_mode=ParseMode.MARKDOWN)
        return

    status_message = await message.reply_text("⏳ *Processing your video...*", parse_mode=ParseMode.MARKDOWN)

    # Set download options with cookies
    ydl_opts = {
        "format": "best",
        "outtmpl": "downloads/%(title)s.%(ext)s",
        "cookiefile": "cookies.txt",  # Pass YouTube cookies for authentication
    }

    try:
        os.makedirs("downloads", exist_ok=True)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        await status_message.edit_text("🚀 *Uploading to Telegram...*", parse_mode=ParseMode.MARKDOWN)

        # Send video
        await client.send_video(
            chat_id=message.chat.id,
            video=file_path,
            caption=f"🎬 *Downloaded Video:* {info['title']}",
            parse_mode=ParseMode.MARKDOWN
        )

        os.remove(file_path)  # Clean up

        await status_message.edit_text("✅ *Video sent successfully!*", parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await status_message.edit_text(f"❌ *Error:* {str(e)}", parse_mode=ParseMode.MARKDOWN)

# Run the bot
if name == "main":
    app.run()
