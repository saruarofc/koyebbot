from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID, MONGO_DB_URI
import motor.motor_asyncio
import aiohttp
import os
import time
import asyncio
from urllib.parse import urlparse

# MongoDB setup
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URI)
db = mongo_client["video_uploader"]
files_collection = db["files"]

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
        print(f'File Uploader Bot Started - {self.username}')

    async def stop(self, *args):
        await super().stop()
        print('File Uploader Bot Stopped')

# Create bot instance
app = Bot()

# Welcome message handler
@app.on_message(filters.command("start") & filters.private)
async def start(client, message: Message):
    welcome_text = "📥 *Welcome to File Uploader Bot!* 📥\n\n" \
                  "Send me any direct download link (e.g., `https://example.com/file.mp4` or YouTube video links), " \
                  "and I’ll upload it to Telegram with progress updates every 5 seconds!"
    await message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

# Function to format progress message
def format_progress(status: str, percentage: float, speed: float, eta: str) -> str:
    return (
        f"📤 *{status}* 📤\n\n"
        f"**Finished**: `{percentage:.1f}%`\n"
        f"**Speed**: `{speed:.2f} MB/s`\n"
        f"**Estimated Time Left**: `{eta}`"
    )

# Handle any direct download link
@app.on_message(filters.text & filters.private)
async def handle_link(client, message: Message):
    url = message.text.strip()
    
    # Basic URL validation
    if not url.startswith(('http://', 'https://')):
        await message.reply_text(
            "❌ Please send a valid URL starting with http:// or https://",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    status_message = await message.reply_text(
        "⏳ *Downloading your file, please wait...* ⏳",
        parse_mode=ParseMode.MARKDOWN
    )
    parsed_url = urlparse(url)
    file_name = f"temp_{message.id}_{os.path.basename(parsed_url.path or 'downloaded_file')}"
    
    try:
        # Download the file with progress tracking and custom headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        async with aiohttp.ClientSession(headers=headers) as session:
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
                                parse_mode=ParseMode.MARKDOWN
                            )
                            await asyncio.sleep(1)  # Prevent flooding
        
        # Upload to Telegram with progress
        await status_message.edit_text(
            "🚀 *Uploading your file to Telegram...* 🚀",
            parse_mode=ParseMode.MARKDOWN
        )
        upload_start_time = time.time()
        uploaded_size = 0
        
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
                    parse_mode=ParseMode.MARKDOWN
                )
                await asyncio.sleep(1)
        
        # Try uploading as video first, fall back to document if it fails
        try:
            sent_message = await client.send_video(
                chat_id=message.chat.id,
                video=file_name,
                caption=f"🎬 Uploaded from: {url}",
                supports_streaming=True,
                progress=upload_progress_tracker
            )
            file_id = sent_message.video.file_id
            is_video = True
        except Exception as video_error:
            # If video upload fails, upload as document
            sent_message = await client.send_document(
                chat_id=message.chat.id,
                document=file_name,
                caption=f"📄 Uploaded from: {url}",
                progress=upload_progress_tracker
            )
            file_id = sent_message.document.file_id
            is_video = False
        
        # Store metadata in MongoDB
        file_data = {
            "user_id": message.from_user.id,
            "url": url,
            "file_id": file_id,
            "is_video": is_video,
            "uploaded_at": message.date
        }
        await files_collection.insert_one(file_data)
        
        # Clean up
        os.remove(file_name)
        
        await status_message.edit_text(
            f"✅ *File uploaded successfully!* ✅\n{'Video' if is_video else 'Document'} is ready!",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        await status_message.edit_text(
            f"❌ *Error*: {str(e)} ❌",
            parse_mode=ParseMode.MARKDOWN
        )
        if os.path.exists(file_name):
            os.remove(file_name)

# Run the bot
if __name__ == "__main__":
    app.run()
