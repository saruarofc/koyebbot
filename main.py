from pyrogram import Client, filters
from pyrogram.types import Message, ChatJoinRequest, InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time

# Import your config variables (you’ll create this file next)
from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID

# Firebase Realtime Database setup (from your provided config)
DB_URL = "https://devz-b17d8-default-rtdb.firebaseio.com"
API_KEY = "AIzaSyC13UFJ7vmhC8WZ9MpbzVfXiJB9TfFGCjs"  # Your API key

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

# Save user data to Firebase
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

# Save chat data to Firebase
def save_chat(chat):
    try:
        url = f"{DB_URL}/chats/{chat.id}.json?auth={API_KEY}"
        data = {
            "title": chat.title or "Unnamed Chat",
            "type": chat.type,
            "added_at": int(time.time())
        }
        response = requests.put(url, json=data)
        if response.status_code != 200:
            print(f"Failed to save chat {chat.id}: {response.text}")
    except Exception as e:
        print(f"Error saving chat: {e}")

# /start command - Show "Pick a Chat" button
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message: Message):
    save_user(message.from_user)
    welcome_text = (
        f"Hello {message.from_user.first_name}! 👋\n"
        "I’m a bot to manage join requests. Click below to pick a chat where I’ll work.\n\n"
        "Commands:\n"
        "/start - Show this message\n"
    )
    if message.from_user.id == OWNER_ID:
        welcome_text += (
            "/s - Show connected chats\n"
            "/u - Show user stats\n"
        )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Pick a Chat", callback_data="pick_chat")]
    ])
    await message.reply_text(welcome_text, reply_markup=keyboard)

# Handle button click - Show user’s chats
@app.on_callback_query(filters.regex("pick_chat"))
async def show_chats(client, callback_query):
    user_id = callback_query.from_user.id
    try:
        # Get all dialogs (chats) the user is part of
        dialogs = await client.get_dialogs()
        chats = []
        for dialog in dialogs:
            chat = dialog.chat
            if chat.type in ["group", "supergroup", "channel"]:
                try:
                    member = await client.get_chat_member(chat.id, user_id)
                    if member.status in ["creator", "administrator"]:
                        chats.append((chat.id, chat.title or "Unnamed Chat"))
                except Exception:
                    pass  # Skip chats where user isn’t a member or can’t be checked

        if not chats:
            await callback_query.edit_message_text("You’re not an admin in any chats I can see, bro. Add me manually somewhere!")
            return

        # Build buttons for each chat
        buttons = [
            [InlineKeyboardButton(title, callback_data=f"select_chat_{chat_id}")]
            for chat_id, title in chats
        ]
        keyboard = InlineKeyboardMarkup(buttons)
        await callback_query.edit_message_text("Pick a chat to add me to:", reply_markup=keyboard)
    except Exception as e:
        await callback_query.edit_message_text(f"Error fetching chats: {e}")

# Handle chat selection - Check permissions or ask to add bot
@app.on_callback_query(filters.regex(r"select_chat_(-?\d+)"))
async def select_chat(client, callback_query):
    chat_id = int(callback_query.data.split("_")[-1])
    try:
        # Check if bot is already in the chat and has the right permissions
        bot_member = await client.get_chat_member(chat_id, (await client.get_me()).id)
        if bot_member.status == "administrator" and bot_member.can_manage_chat:  # Using can_manage_chat as a proxy for join request perms
            app.connected_chats.add(chat_id)
            chat = await client.get_chat(chat_id)
            save_chat(chat)
            await callback_query.edit_message_text(f"I’m already an admin in {chat.title or 'this chat'} with the right perms! Ready to go.")
            return
        elif bot_member.status == "administrator":
            await callback_query.edit_message_text(
                f"I’m an admin in {chat.title or 'this chat'}, but I need 'Approve New Members' permission. Update my perms!"
            )
            return
    except Exception:
        # Bot isn’t in the chat or not admin yet
        pass

    # Bot isn’t in the chat - ask user to add it with specific permissions
    chat = await client.get_chat(chat_id)
    await callback_query.edit_message_text(
        f"Add me (@{app.username}) as an admin to {chat.title or 'this chat'} with 'Approve New Members' permission.\n"
        "I’ll confirm once I’m set up!"
    )

# Handle bot being added as admin - Check permissions
@app.on_chat_member_updated()
async def on_member_updated(client, update):
    if update.new_chat_member and update.new_chat_member.user.id == (await client.get_me()).id:
        if update.new_chat_member.status == "administrator":
            chat_id = update.chat.id
            if update.new_chat_member.can_manage_chat:  # Proxy for join request permission
                app.connected_chats.add(chat_id)
                save_chat(update.chat)
                try:
                    await client.send_message(
                        update.from_user.id,
                        f"✅ Success! I’m now an admin in {update.chat.title or 'this chat'} with the right permissions."
                    )
                except Exception as e:
                    print(f"Error sending success message: {e}")
            else:
                try:
                    await client.send_message(
                        update.from_user.id,
                        f"I’m in {update.chat.title or 'this chat'}, but I need 'Approve New Members' permission. Fix my perms!"
                    )
                except Exception as e:
                    print(f"Error sending permission request: {e}")

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
