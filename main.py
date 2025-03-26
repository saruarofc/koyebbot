from pyrogram import Client, filters
from pyrogram.types import Message, ChatJoinRequest
from firebase_admin import credentials, db, initialize_app
import os

# Import your config variables
from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID

# Initialize Firebase with the service account key for Realtime Database
try:
    cred = credentials.Certificate("path/to/your/serviceAccountKey.json")  # Update this path
    initialize_app(cred, {
        'databaseURL': 'https://devz-b17d8-default-rtdb.firebaseio.com'  # Your RTDB URL
    })
    # Reference to the root of the Realtime Database
    root_ref = db.reference()
except Exception as e:
    print(f"Error initializing Firebase: {e}")
    exit(1)

# References to specific paths in RTDB
users_ref = root_ref.child('users')
chats_ref = root_ref.child('chats')

# Initialize the bot
class Bot(Client):
    def __init__(self):
        super().__init__(
            "join_request_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=10,
            sleep_threshold=10
        )
        self.connected_chats = set()

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.username = '@' + me.username
        print(f'Join Request Bot Started - {self.username}')

    async def stop(self, *args):
        await super().stop()
        print('Join Request Bot Stopped')

# Create bot instance
app = Bot()

# Store user data in RTDB
def save_user(user):
    try:
        users_ref.child(str(user.id)).update({
            "name": user.first_name or "Unknown",
            "username": user.username or "N/A",
            "joined_at": db.ServerValue.TIMESTAMP  # Server-side timestamp
        })
    except Exception as e:
        print(f"Error saving user to RTDB: {e}")

# Store chat data in RTDB
def save_chat(chat):
    try:
        chats_ref.child(str(chat.id)).update({
            "title": chat.title or "Unnamed Chat",
            "type": chat.type,
            "added_at": db.ServerValue.TIMESTAMP  # Server-side timestamp
        })
    except Exception as e:
        print(f"Error saving chat to RTDB: {e}")

# /start command
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message: Message):
    save_user(message.from_user)
    welcome_text = (
        f"Hello {message.from_user.first_name}! 👋\n"
        "I’m a bot to manage join requests. Here are my commands:\n\n"
        "/start - Show this message\n"
        "/add - Add me as an admin to your group/channel\n"
    )
    if message.from_user.id == OWNER_ID:
        welcome_text += (
            "/s - Show connected chats\n"
            "/u - Show user stats\n"
        )
    await message.reply_text(welcome_text)

# /add command
@app.on_message(filters.command("add") & filters.private)
async def add_command(client, message: Message):
    save_user(message.from_user)
    await message.reply_text(
        "To use me, add me as an admin to your group or channel:\n"
        "1. Go to your chat settings.\n"
        "2. Add me (@YourBotUsername) as an admin with 'Approve New Members' permission.\n"
        "3. I’ll confirm once I’m added!"
    )

# Handle bot being added as admin
@app.on_chat_member_updated()
async def on_member_updated(client, update):
    if update.new_chat_member and update.new_chat_member.user.id == (await client.get_me()).id:
        if update.new_chat_member.status == "administrator":
            chat_id = update.chat.id
            app.connected_chats.add(chat_id)
            save_chat(update.chat)
            try:
                await client.send_message(
                    update.from_user.id,
                    f"✅ Success! I’ve been added as an admin to {update.chat.title or 'this chat'}."
                )
            except Exception as e:
                print(f"Error sending success message: {e}")

# Handle join requests
@app.on_chat_join_request()
async def handle_join_request(client, join_request: ChatJoinRequest):
    chat_id = join_request.chat.id
    if chat_id in app.connected_chats:
        try:
            await client.approve_chat_join_request(chat_id, join_request.from_user.id)
            save_user(join_request.from_user)
            await client.send_message(
                join_request.from_user.id,
                f"🎉 You are approved! Welcome to {join_request.chat.title or 'the chat'}!"
            )
        except Exception as e:
            print(f"Error approving join request: {e}")

# /s command (owner only) - Show connected chats
@app.on_message(filters.command("s") & filters.private & filters.user(OWNER_ID))
async def show_chats(client, message: Message):
    try:
        chats = chats_ref.get() or {}
        if chats:
            chat_list = "\n".join([f"- {chat_data['title']} (ID: {chat_id})" for chat_id, chat_data in chats.items()])
            await message.reply_text(f"Connected chats:\n{chat_list}")
        else:
            await message.reply_text("No chats connected yet.")
    except Exception as e:
        await message.reply_text(f"Error fetching chats: {e}")

# /u command (owner only) - Show user stats
@app.on_message(filters.command("u") & filters.private & filters.user(OWNER_ID))
async def show_user_stats(client, message: Message):
    try:
        users = users_ref.get() or {}
        user_count = len(users)
        await message.reply_text(f"Total users: {user_count}")
    except Exception as e:
        await message.reply_text(f"Error fetching user stats: {e}")

# Run the bot
if __name__ == "__main__":
    required_vars = {"API_ID": API_ID, "API_HASH": API_HASH, "BOT_TOKEN": BOT_TOKEN, "OWNER_ID": OWNER_ID}
    for var_name, var_value in required_vars.items():
        if not var_value:
            print(f"Error: {var_name} is not set in config.py")
            exit(1)
    app.run()
