from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
import os
import yt_dlp
import asyncio
import time

from config import API_ID, API_HASH, BOT_TOKEN

# Initialize the bot
class Bot(Client):
    def __init__(self):
        super().__init__(
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

    if not url.startswith(("http://", "https://")):
        await message.reply_text("❌ Please send a valid video link!", parse_mode=ParseMode.MARKDOWN)
        return

    status_message = await message.reply_text("⏳ *Processing your video...*", parse_mode=ParseMode.MARKDOWN)

    os.makedirs("downloads", exist_ok=True)
    download_status = {"last_update": 0, "message": status_message}

    def progress_hook(d):
        if d['status'] == 'downloading':
            downloaded = d.get('downloaded_bytes', 0) / (1024 * 1024)  # Convert to MB
            total_size = d.get('total_bytes', 1) / (1024 * 1024)  # Convert to MB
            percentage = d.get('_percent_str', '0%').strip()
            speed = d.get('_speed_str', 'N/A')
            eta = d.get('_eta_str', 'N/A')

            bar_length = 10
            progress_blocks = int((downloaded / total_size) * bar_length) if total_size > 0 else 0
            progress_bar = "▓" * progress_blocks + "░" * (bar_length - progress_blocks)

            progress_text = (
                f"📥 *Downloading...*\n\n"
                f"🔹 [{progress_bar}] | *{percentage}*\n\n"
                f"📁 *Total Size:* {total_size:.2f} MiB\n"
                f"📀 *Downloaded:* {downloaded:.2f} MiB\n"
                f"🚀 *Speed:* {speed}\n"
                f"🕔 *Time Remaining:* {eta}s"
            )

            # Update message every 5 seconds
            if time.time() - download_status["last_update"] > 5:
                asyncio.create_task(download_status["message"].edit_text(progress_text, parse_mode=ParseMode.MARKDOWN))
                download_status["last_update"] = time.time()

    ydl_opts = {
        "format": "best",
        "outtmpl": "downloads/%(title)s.%(ext)s",
        "progress_hooks": [progress_hook],  # Attach progress hook
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        await status_message.edit_text("🚀 *Uploading to Telegram...*", parse_mode=ParseMode.MARKDOWN)

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

if __name__ == "__main__":
    app.run()
