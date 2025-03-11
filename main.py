from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID, MONGO_DB_URI
import motor.motor_asyncio
import aiohttp
import os
import time
import asyncio
from urllib.parse import urlparse

# MongoDB setup (optional, for storing uploaded video metadata)
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URI)
db = mongo_client["video_uploader"]
videos_collection = db["videos"]

class Bot(Client):
    def __init__(self):
        super().__init__(
            "video_uploader_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=150,
            sleep_threshold=10
        )

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.username = '@' + me.username
        print(f'Video Uploader Bot Started - {self.username}')

    async def stop(self, *args):
        await super().stop()
        print('Video Uploader Bot Stopped')

# Create bot instance
app = Bot()

# Welcome message handler
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    welcome_text = "🎥 *Welcome to Video Uploader Bot!* 🎥\n\n" \
                  "Send me a direct video link (e.g., `https://example.com/video.mp4`), " \
                  "and I’ll upload it to Telegram with progress updates every 5 seconds!"
    await message.reply_text(welcome_text, parse_mode="markdown")

# Function to format progress message
def format_progress(status: str, percentage: float, speed: float, eta: str) -> str:
    return (
        f"📤 *{status}* 📤\n\n"
        f"**Finished**: `{percentage:.1f}%`\n"
        f"**Speed**: `{speed:.2f} MB/s`\n"
        f"**Estimated Time Left**: `{eta}`"
    )

# Handle direct video links
@app.on_message(filters.text & filters.private)
async def handle_link(client, message: Message):
    url = message.text.strip()
    
    # Basic URL validation
    if not url.startswith(('http://', 'https://')):
        await message.reply_text("❌ Please send a valid URL starting with http:// or https://", parse_mode="markdown")
        return
    
    # Check if it’s likely a video link by extension
    video_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.wmv')
    parsed_url = urlparse(url)
    if not parsed_url.path.lower().endswith(video_extensions):
        await message.reply_text(
            "❌ Please send a direct link to a video file (e.g., .mp4, .mkv, .avi, .mov, .wmv)",
            parse_mode="markdown"
        )
        return
    
    status_message = await message.reply_text("⏳ *Downloading your video, please wait...* ⏳", parse_mode="markdown")
    file_name = f"temp_{message.id}_{os.path.basename(parsed_url.path)}"
    
    try:
        # Download the video with progress tracking
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise Exception(f"Failed to download: HTTP {resp.status}")
                
                total_size = int(resp.headers.get('Content-Length', 0)) / 1024 / 1024  # Size in MB
                downloaded_size = 0
                start_time = time.time()
                
                with open(file_name, 'wb') as f:
                    async for chunk in resp.content.iter_chunked(1024 * 1024):  # 1MB chunks
                        downloaded_size += len(chunk) / 1024 / 1024  # Update size in MB
                        f.write(chunk)
                        
                        # Calculate progress
                        percentage = (downloaded_size / total_size) * 100 if total_size > 0 else 0
                        elapsed_time = time.time() - start_time
                        speed = downloaded_size / elapsed_time if elapsed_time > 0 else 0
                        eta = (
                            f"{int((total_size - downloaded_size) / speed)}s"
                            if speed > 0 and total_size > downloaded_size
                            else "Calculating..."
                        )
                        
                        # Update status every 5 seconds
                        if int(elapsed_time) % 5 == 0 or percentage >= 100:
                            await status_message.edit_text(
                                format_progress("Downloading", percentage, speed, eta),
                                parse_mode="markdown"
                            )
                            await asyncio.sleep(1)  # Prevent flooding
        
        # Upload video to Telegram with progress
        await status_message.edit_text("🚀 *Uploading your video to Telegram...* 🚀", parse_mode="markdown")
        upload_start_time = time.time()
        uploaded_size = 0
        
        # Simulate upload progress (Telegram doesn’t provide real-time upload progress)
        async def upload_progress_tracker(current, total):
            nonlocal uploaded_size, upload_start_time
            uploaded_size = current / 1024 / 1024  # Convert to MB
            percentage = (uploaded_size / total_size) * 100
            elapsed_time = time.time() - upload_start_time
            speed = uploaded_size / elapsed_time if elapsed_time > 0 else 0
            eta = (
                f"{int((total_size - uploaded_size) / speed)}s"
                if speed > 0 and total_size > uploaded_size
                else "Calculating..."
            )
            
            if int(elapsed_time) % 5 == 0 or percentage >= 100:
                await status_message.edit_text(
                    format_progress("Uploading", percentage, speed, eta),
                    parse_mode="markdown"
                )
                await asyncio.sleep(1)
        
        sent_message = await client.send_video(
            chat_id=message.chat.id,
            video=file_name,
            caption=f"🎬 Uploaded from: {url}",
            supports_streaming=True,
            progress=upload_progress_tracker
        )
        
        # Store metadata in MongoDB
        video_data = {
            "user_id": message.from_user.id,
            "url": url,
            "file_id": sent_message.video.file_id,
            "uploaded_at": message.date
        }
        await videos_collection.insert_one(video_data)
        
        # Clean up
        os.remove(file_name)
        
        await status_message.edit_text(
            "✅ *Video uploaded successfully!* ✅\nEnjoy your video!",
            parse_mode="markdown"
        )
        
    except Exception as e:
        await status_message.edit_text(f"❌ *Error*: {str(e)} ❌", parse_mode="markdown")
        if os.path.exists(file_name):
            os.remove(file_name)

# Run the bot
if __name__ == "__main__":
    app.run()
