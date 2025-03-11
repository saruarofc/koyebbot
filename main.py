import os
import time
import yt_dlp
from PIL import Image
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
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


app = Bot()


# Welcome message
@app.on_message(filters.command("start") & filters.private)
async def start(client, message: Message):
    welcome_text = (
        "🎥 *Welcome to Video Downloader Bot!* 🎥\n\n"
        "Send me a YouTube link, and I'll download and send the video to you!"
    )
    await message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)


# Function to track progress
async def progress_callback(current, total, message, start_time):
    elapsed_time = time.time() - start_time
    speed = current / elapsed_time if elapsed_time > 0 else 0
    remaining_time = (total - current) / speed if speed > 0 else 0

    percent = current * 100 / total
    progress = "▓" * int(percent / 5) + "░" * (20 - int(percent / 5))

    status_text = (
        f"UPLOADING:\n\n"
        f"[{progress}] | {percent:.2f}%\n\n"
        f"📁 Tᴏᴛᴀʟ Sɪᴢᴇ: {total / (1024 * 1024):.2f} MiB\n"
        f"🚀 Sᴘᴇᴇᴅ: {speed / (1024 * 1024):.2f} MiB/s\n"
        f"🕔 Tɪᴍᴇ: {int(remaining_time // 60)}m {int(remaining_time % 60)}s"
    )
    await message.edit_text(status_text)


# Handle video links
@app.on_message(filters.text & filters.private)
async def download_video(client, message: Message):
    url = message.text.strip()

    # Validate URL
    if not url.startswith(("http://", "https://")):
        await message.reply_text("❌ Please send a valid video link!", parse_mode=ParseMode.MARKDOWN)
        return

    status_message = await message.reply_text("⏳ *Processing your video...*", parse_mode=ParseMode.MARKDOWN)

    # Set download options with thumbnail
    ydl_opts = {
        "format": "best",
        "outtmpl": "downloads/%(title)s.%(ext)s",
        "writethumbnail": True,  # Ensure thumbnail is downloaded
        "merge_output_format": "mp4",
    }

    try:
        os.makedirs("downloads", exist_ok=True)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            thumb_path = file_path.rsplit(".", 1)[0] + ".webp"  # Thumbnail path

            # Convert .webp to .jpg if necessary
            if os.path.exists(thumb_path):
                new_thumb_path = thumb_path.replace(".webp", ".jpg")
                Image.open(thumb_path).convert("RGB").save(new_thumb_path, "JPEG")
                os.remove(thumb_path)
                thumb_path = new_thumb_path  # Use converted thumbnail

        await status_message.edit_text("🚀 *Uploading to Telegram...*", parse_mode=ParseMode.MARKDOWN)

        # Track upload time
        start_time = time.time()

        async def upload_progress(current, total):
            await progress_callback(current, total, status_message, start_time)

        await client.send_video(
            chat_id=message.chat.id,
            video=file_path,
            caption=f"🎬 *Downloaded Video:* {info['title']}",
            parse_mode=ParseMode.MARKDOWN,
            thumb=thumb_path if os.path.exists(thumb_path) else None,  # Attach valid thumbnail
            progress=upload_progress,
        )

        # Cleanup
        os.remove(file_path)
        if os.path.exists(thumb_path):
            os.remove(thumb_path)

        await status_message.edit_text("✅ *Video sent successfully!*", parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await status_message.edit_text(f"❌ *Error:* {str(e)}", parse_mode=ParseMode.MARKDOWN)


# Run the bot
if __name__ == "__main__":
    app.run()
