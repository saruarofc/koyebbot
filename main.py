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
        "🎥 Welcome to Video Downloader Bot! 🎥\n\n"
        "Send me a YouTube link, and I'll download and send the video to you!"
    )
    await message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

# Progress callback function
def progress_hook(d):
    if d['status'] == 'downloading':
        global download_progress
        download_progress = {
            'percentage': float(d.get('_percent_str', '0%').strip('%')),
            'total_size': d.get('total_bytes', 0),
            'downloaded': d.get('downloaded_bytes', 0),
            'speed': d.get('speed', 0),
            'eta': d.get('eta', 0)
        }

# Handle video links
@app.on_message(filters.text & filters.private)
async def download_video(client, message: Message):
    url = message.text.strip()

    # Validate URL  
    if not url.startswith(("http://", "https://")):  
        await message.reply_text("❌ Please send a valid video link!", parse_mode=ParseMode.MARKDOWN)  
        return  

    status_message = await message.reply_text("⏳ *Processing your video...*", parse_mode=ParseMode.MARKDOWN)  

    # Set download options with cookies and thumbnail
    ydl_opts = {  
        "format": "bestvideo+bestaudio/best",  # Ensures best quality with audio
        "outtmpl": "downloads/%(title)s.%(ext)s",
        "cookiefile": "cookies.txt",
        "writethumbnail": True,  # Write thumbnail to disk
        "embedthumbnail": True,  # Embed thumbnail in video
        "merge_output_format": "mp4",  # Ensure output is mp4
        "progress_hooks": [progress_hook],  # Add progress hook
    }

    try:  
        os.makedirs("downloads", exist_ok=True)  
        global download_progress
        download_progress = {}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  
            info = ydl.extract_info(url, download=True)  
            file_path = ydl.prepare_filename(info)  

            # Start progress update task
            async def update_progress():
                while download_progress.get('percentage', 0) < 100:
                    if download_progress:
                        # Calculate progress bar
                        progress = download_progress['percentage']
                        bars = int(progress / 10)
                        progress_bar = '[' + '▓' * bars + '░' * (10 - bars) + ']'
                        
                        # Format sizes
                        downloaded_mb = download_progress['downloaded'] / 1024 / 1024
                        total_mb = download_progress['total_size'] / 1024 / 1024
                        
                        # Format speed
                        speed_mb = download_progress['speed'] / 1024 / 1024 if download_progress['speed'] else 0
                        
                        # Format ETA
                        eta = download_progress['eta'] or 0
                        eta_min = eta // 60
                        eta_sec = eta % 60

                        progress_text = (
                            "DOWNLOADING:\n\n"
                            f"{progress_bar} | {progress:.2f}%\n\n"
                            f"📁 Tᴏᴛᴀʟ Sɪᴢᴇ: {downloaded_mb:.1f} MiB out of {total_mb:.1f} MiB\n"
                            f"🚀 Sᴘᴇᴇᴅ: {speed_mb:.2f} MiB/s\n"
                            f"🕔 Tɪᴍᴇ: {eta_min}m, {eta_sec}s"
                        )
                        await status_message.edit_text(progress_text, parse_mode=ParseMode.MARKDOWN)
                    await asyncio.sleep(5)  # Update every 5 seconds

            # Run progress updates concurrently
            progress_task = asyncio.create_task(update_progress())
            
            # Wait for download to complete
            while download_progress.get('percentage', 0) < 100:
                await asyncio.sleep(1)

            # Cancel progress task and update status
            progress_task.cancel()
            await status_message.edit_text("🚀 *Uploading to Telegram...*", parse_mode=ParseMode.MARKDOWN)  

        # Send video with thumbnail
        await client.send_video(  
            chat_id=message.chat.id,  
            video=file_path,  
            caption=f"🎬 *Downloaded Video:* {info['title']}",  
            parse_mode=ParseMode.MARKDOWN,
            thumb=f"{file_path.rsplit('.', 1)[0]}.jpg" if os.path.exists(f"{file_path.rsplit('.', 1)[0]}.jpg") else None
        )  

        # Clean up
        os.remove(file_path)  
        if os.path.exists(f"{file_path.rsplit('.', 1)[0]}.jpg"):
            os.remove(f"{file_path.rsplit('.', 1)[0]}.jpg")
        
        await status_message.edit_text("✅ *Video sent successfully!*", parse_mode=ParseMode.MARKDOWN)  

    except Exception as e:  
        await status_message.edit_text(f"❌ *Error:* {str(e)}", parse_mode=ParseMode.MARKDOWN)

# Run the bot
if __name__ == "__main__":
    app.run()
