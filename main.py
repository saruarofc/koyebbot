from pyrogram import Client, filters
from pyrogram.types import Message, ChatJoinRequest
import requests
import time

# Import your config variables
from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID

# Firebase Realtime Database setup
DB_URL = "https://devz-b17d8-default-rtdb.firebaseio.com"
API_KEY = "AIzaSyC13UFJ7vmhC8WZ9MpbzVfXiJB9TfFGCjs"

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
        self.waiting_for_chat = {}  # Track users waiting to send forwarded message

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

# Save user data to Firebase Realtime Database
def save_user(user):
    try:
        url = f"{DB_URL}/users/{user.id}.json?auth={API_KEY}"
        data = {
            "name": user.first_name or "Unknown",
            "username": user.username or "N/A",
            "joined_at": int(time.time())
        }
        response = requests.put(url, json=data)
        if response.status_code != 200:
            print(f"Failed to save user {user.id}: {response.text}")
    except Exception as e:
        print(f"Error saving user: {e}")

# Save chat data to Firebase Realtime Database
def save_chat(chat_id, title, chat_type):
    try:
        url = f"{DB_URL}/chats/{chat_id}.json?auth={API_KEY}"
        data = {
            "title": title or "Unnamed Chat",
            "type": chat_type,
            "added_at": int(time.time())
        }
        response = requests.put(url, json=data)
        if response.status_code != 200:
            print(f"Failed to save chat {chat_id}: {response.text}")
    except Exception as e:
        print(f"Error saving chat: {e}")

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
    user_id = message.from_user.id
    save_user(message.from_user)
    app.waiting_for_chat[user_id] = True  # Mark user as waiting for forwarded message
    await message.reply_text(
        "Here’s the deal:\n"
        "1. Add me as an admin to your group/channel with 'Approve New Members' permission.\n"
        "2. Forward any message from that chat to me (with the 'Forwarded from' tag).\n"
        "I’ll check it and confirm!"
    )

# Handle forwarded message from user
@app.on_message(filters.private & filters.forwarded)
async def handle_forwarded_message(client, message: Message):
    user_id = message.from_user.id
    if user_id not in app.waiting_for_chat:
        await message.reply_text("Yo, use /add first so I know what’s up!")
        return

    if not message.forward_from_chat:
        await message.reply_text("Bro, forward a message from the chat with the 'Forwarded from' tag!")
        return

    chat_id = message.forward_from_chat.id
    chat_title = message.forward_from_chat.title
    chat_type = message.forward_from_chat.type

    try:
        # Check if bot is an admin in that chat
        bot_member = await client.get_chat_member(chat_id, (await client.get_me()).id)
        if bot_member.status not in ["administrator", "creator"]:
            await message.reply_text("I’m not an admin there! Give me 'Approve New Members' permission and try again.")
            return

        # Bot is admin—save it and confirm
        app.connected_chats.add(chat_id)
        save_chat(chat_id, chat_title, chat_type)
        await message.reply_text(f"✅ Success! I’m an admin in {chat_title or 'this chat'} and good to go.")
        del app.waiting_for_chat[user_id]  # Done with this user

    except Exception as e:
        print(f"Error checking chat: {e}")
        await message.reply_text("Something went wrong—make sure I’m in the chat and try again.")

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
        response = requests.get(f"{DB_URL}/chats.json?auth={API_KEY}")
        chats = response.json() or {}
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
        response = requests.get(f"{DB_URL}/users.json?auth={API_KEY}")
        users = response.json() or {}
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
