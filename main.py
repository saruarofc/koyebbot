from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient
import os

from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID, MONGO_DB_URI

# Initialize MongoDB
mongo_client = MongoClient(MONGO_DB_URI)
db = mongo_client["movie_store"]
videos_collection = db["videos"]
users_collection = db["users"]

# Admin Channel ID
ADMIN_CHANNEL_ID = -1002006884073  # Replace with your channel ID

# Initialize the bot
class Bot(Client):
    def __init__(self):
        super().__init__(
            "movie_store_bot",
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
        print(f'Movie Store Bot Started - {self.username}')

    async def stop(self, *args):
        await super().stop()
        print('Movie Store Bot Stopped')

# Create bot instance
app = Bot()

# Store user data
def save_user(user):
    users_collection.update_one(
        {"user_id": user.id},
        {"$set": {"name": user.first_name, "username": user.username}},
        upsert=True
    )

# Welcome message
@app.on_message(filters.command("start") & filters.private)
async def start(client, message: Message):
    user_id = message.from_user.id
    save_user(message.from_user)

    if user_id == OWNER_ID:
        admin_text = (
            "🛠 *Admin Commands:*\n"
            "📤 Upload videos to store them\n"
            "🎬 Send video to admin channel"
        )
        await message.reply_text(admin_text)
    else:
        welcome_text = (
            "🎬 *Welcome to Movie Store Bot!* 🎬\n\n"
            "🎥 Upload or request any movie."
        )
        await message.reply_text(welcome_text)

# Upload video and get a link
@app.on_message(filters.video & filters.private)
async def handle_video(client, message: Message):
    video = message.video.file_id
    caption = message.caption if message.caption else "No description"
    title = caption.split("\n")[0] if "\n" in caption else caption
    uploader = message.from_user

    # Forward video to the admin channel
    forwarded = await client.forward_messages(ADMIN_CHANNEL_ID, message.chat.id, message.message_id)

    # Get file path from Telegram API
    file_info = await client.get_file(video)
    file_path = file_info.file_path

    # Generate temporary link
    temp_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    # Save video data in MongoDB
    videos_collection.insert_one({
        "video_id": video,
        "title": title,
        "description": caption,
        "uploaded_by": uploader.id,
        "views": 0,
        "file_path": file_path
    })

    await message.reply_text(f"✅ *Video uploaded and sent to admin channel!*\n\n📥 [Download Video]({temp_link})\n⚠️ *This link is valid for ~1 hour!*", disable_web_page_preview=True)

# Run the bot
if __name__ == "__main__":
    app.run()
