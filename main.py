from pyrogram import Client, filters
from pyrogram.types import Message, Video
from pymongo import MongoClient
import os

from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID, MONGO_DB_URI

# Initialize MongoDB
mongo_client = MongoClient(MONGO_DB_URI)
db = mongo_client["movie_store"]
videos_collection = db["videos"]
users_collection = db["users"]

# Admin Channel ID
ADMIN_CHANNEL_ID = -1002006884073

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
            "📊 `/u` - List all users\n"
            "🎬 `/i` - List all forwarded videos\n"
            "➕ Upload videos to store them\n"
            "📤 Forward videos to send them for review"
        )
        await message.reply_text(admin_text)
    else:
        welcome_text = (
            "🎬 *Welcome to Movie Store Bot!* 🎬\n\n"
            "🔍 Search for any movie by typing its name.\n"
            "🎥 Browse our collection and enjoy!"
        )
        await message.reply_text(welcome_text)

# Search for videos
@app.on_message(filters.text & filters.private)
async def search_movie(client, message: Message):
    query = message.text.strip()
    movie = videos_collection.find_one({"title": {"$regex": query, "$options": "i"}})

    if movie:
        await message.reply_video(
            movie["video_id"],
            caption=f"🎬 *{movie['title']}*\n📜 {movie['description']}\n📊 Views: {movie['views'] + 1}"
        )
        videos_collection.update_one({"_id": movie["_id"]}, {"$inc": {"views": 1}})
    else:
        await message.reply_text("❌ Sorry, movie not found.\n📥 We will try to add it soon!")

# Store and forward received videos
@app.on_message(filters.video & filters.private)
async def handle_video(client, message: Message):
    video = message.video.file_id
    caption = message.caption if message.caption else "No description"
    title = caption.split("\n")[0] if "\n" in caption else caption
    uploader = message.from_user

    # Save video data
    videos_collection.insert_one({
        "video_id": video,
        "title": title,
        "description": caption,
        "uploaded_by": uploader.id,
        "views": 0
    })

    # Forward to admin channel
    forwarded = await client.forward_messages(ADMIN_CHANNEL_ID, message.chat.id, message.message_id)
    
    await message.reply_text("✅ *Video stored and sent to admin!*")

# Forwarded videos to admin channel
@app.on_message(filters.forwarded & filters.private)
async def forward_to_admin(client, message: Message):
    if message.video:
        forwarded = await client.forward_messages(ADMIN_CHANNEL_ID, message.chat.id, message.message_id)
        videos_collection.insert_one({
            "video_id": message.video.file_id,
            "title": "Forwarded Video",
            "description": "User forwarded this video.",
            "uploaded_by": message.from_user.id,
            "views": 0
        })
        await message.reply_text("📤 *Video sent to admin for review!*")

# Admin: List stored user data
@app.on_message(filters.command("u") & filters.user(OWNER_ID))
async def list_users(client, message: Message):
    users = list(users_collection.find({}, {"_id": 0}))
    
    if users:
        user_list = "\n".join([f"👤 {user['name']} (@{user['username']})" for user in users])
        await message.reply_text(f"📊 *Registered Users:*\n{user_list}")
    else:
        await message.reply_text("❌ No users found.")

# Admin: List previously forwarded videos
@app.on_message(filters.command("i") & filters.user(OWNER_ID))
async def list_forwarded_videos(client, message: Message):
    videos = list(videos_collection.find({}, {"_id": 0, "video_id": 1, "title": 1}))

    if videos:
        video_list = "\n".join([f"🎬 {video['title']}" for video in videos])
        await message.reply_text(f"📜 *Stored Videos:*\n{video_list}")
    else:
        await message.reply_text("❌ No videos found.")

# Run the bot
if __name__ == "__main__":
    app.run()
