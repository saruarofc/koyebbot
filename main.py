from pyrogram import Client, filters
from pyrogram.types import Message, Video
from pymongo import MongoClient
import os
import asyncio

from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID, MONGO_DB_URI

# Initialize MongoDB
mongo_client = MongoClient(MONGO_DB_URI)
db = mongo_client["movie_store"]
videos_collection = db["videos"]
requests_collection = db["requests"]

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

# Welcome message
@app.on_message(filters.command("start") & filters.private)
async def start(client, message: Message):
    welcome_text = (
        "🎬 *Welcome to Movie Store Bot!* 🎬\n\n"
        "🔍 Search for any movie by typing its name.\n"
        "🎥 Browse our collection and enjoy!"
    )
    await message.reply_text(welcome_text)

# Search for videos in the database
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
        requests_collection.insert_one({"user_id": message.from_user.id, "query": query})
        await message.reply_text(
            "❌ Sorry, we couldn’t find this movie.\n📥 Your request has been recorded!"
        )

# Admin - Upload videos
@app.on_message(filters.video & filters.user(OWNER_ID))
async def add_video(client, message: Message):
    video = message.video.file_id
    caption = message.caption if message.caption else "No description"
    title = caption.split("\n")[0] if "\n" in caption else caption

    videos_collection.insert_one({
        "video_id": video,
        "title": title,
        "description": caption,
        "uploaded_by": message.from_user.id,
        "views": 0,
        "requests": 0
    })

    await message.reply_text("✅ *Video added to the store!*")

# Forwarded videos for admin review
@app.on_message(filters.forwarded & filters.private)
async def forward_to_admin(client, message: Message):
    if message.video:
        await client.send_message(
            ADMIN_CHANNEL_ID,  # Forward to admin channel
            "📩 *New Forwarded Video for Review!*",
            reply_to_message_id=message.message_id
        )
        await message.reply_text("📤 *Video sent to admin for approval!*")

# Edit video details (Admin Only)
@app.on_message(filters.command("edit") & filters.user(OWNER_ID))
async def edit_video(client, message: Message):
    try:
        _, old_title, new_title = message.text.split(" | ")
        videos_collection.update_one({"title": old_title}, {"$set": {"title": new_title}})
        await message.reply_text(f"✅ *Updated movie title from '{old_title}' to '{new_title}'!*")
    except:
        await message.reply_text("❌ *Invalid format! Use: /edit OldTitle | NewTitle*")

# Delete videos (Admin Only)
@app.on_message(filters.command("delete") & filters.user(OWNER_ID))
async def delete_video(client, message: Message):
    _, title = message.text.split(" ", 1)
    result = videos_collection.delete_one({"title": title})

    if result.deleted_count:
        await message.reply_text(f"✅ *Movie '{title}' deleted!*")
    else:
        await message.reply_text("❌ *Movie not found!*")

# Notify users when requested movie is added
async def notify_users(title):
    requests = requests_collection.find({"query": {"$regex": title, "$options": "i"}})
    
    for request in requests:
        try:
            await app.send_message(request["user_id"], f"🎬 *Good news!*\nThe movie '{title}' has been added!")
        except:
            pass

    requests_collection.delete_many({"query": {"$regex": title, "$options": "i"}})

# Run the bot
if __name__ == "__main__":
    app.run()
