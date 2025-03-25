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

# Handle all messages, including video
@app.on_message(filters.private)
async def handle_all_messages(client, message: Message):
    # Save user data on first interaction
    save_user(message.from_user)

    # Check if the message contains a video
    if message.video:
        print(f"Received video from {message.from_user.id}")  # Log for debugging
        video = message.video.file_id
        caption = message.caption if message.caption else "No description"
        title = caption.split("\n")[0] if "\n" in caption else caption
        uploader = message.from_user

        try:
            # Forward the video to the admin channel
            forwarded = await client.forward_messages(ADMIN_CHANNEL_ID, message.chat.id, message.message_id)
            print(f"Video forwarded to admin channel {ADMIN_CHANNEL_ID}")  # Log forwarding

            # Get file path from Telegram API
            file_info = await client.get_file(video)
            file_path = file_info.file_path
            print(f"File path: {file_path}")  # Log the file path

            # Generate temporary download link
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

            # Send temporary download link to the user
            await message.reply_text(
                f"✅ *Video uploaded and sent to admin channel!*\n\n📥 [Download Video]({temp_link})\n⚠️ *This link is valid for ~1 hour!*",
                disable_web_page_preview=True
            )

        except Exception as e:
            print(f"Error while processing video: {e}")  # Log error if any
            await message.reply_text("❌ There was an error while processing the video.")
    
    else:
        # Handle non-video messages
        await message.reply_text("📥 Please send a video to store it and get a temporary link.")

# Run the bot
if __name__ == "__main__":
    app.run()
