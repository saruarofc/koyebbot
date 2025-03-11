from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID, MONGO_DB_URI
import motor.motor_asyncio

# MongoDB setup
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URI)
db = mongo_client["telegram_bot_manager"]
bots_collection = db["bots"]

class Bot(Client):
    def __init__(self):
        super().__init__(
            "manager_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=150,
            sleep_threshold=10
        )
        self.running_bots = {}  # Store hosted bot instances
        self.message_map = {}   # Store message mappings globally

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.username = '@' + me.username
        print(f'Bot Manager Started - {self.username}')

    async def stop(self, *args):
        for token, bot in self.running_bots.items():
            await bot.stop()
        await super().stop()
        print('Bot Manager Stopped')

# Create main bot instance
app = Bot()

# Welcome message handler
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    buttons = [
        [InlineKeyboardButton("Add Bot", callback_data="add_bot")],
        [InlineKeyboardButton("Existing Bots", callback_data="existing_bots")]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    welcome_text = "Welcome to Bot Manager!\n\n" \
                  "Use the buttons below to manage your bots:"
    
    await message.reply_text(welcome_text, reply_markup=reply_markup)

# Button handler
@app.on_callback_query()
async def button_handler(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data

    if data == "add_bot":
        await callback_query.edit_message_text(
            "Please send your Bot Token to add a new bot."
        )
        client.state = {"awaiting_token": True, "user_id": user_id}
    
    elif data == "existing_bots":
        user_bots = await bots_collection.find({"admin_id": user_id}).to_list(None)
        
        if not user_bots:
            await callback_query.edit_message_text("You haven't added any bots yet!")
        else:
            buttons = []
            for bot_data in user_bots:
                bot_name = bot_data["bot_name"]
                buttons.append([
                    InlineKeyboardButton(bot_name, callback_data=f"view_{bot_name}"),
                    InlineKeyboardButton("Remove", callback_data=f"remove_{bot_name}")
                ])
            reply_markup = InlineKeyboardMarkup(buttons)
            await callback_query.edit_message_text("Your Bots:", reply_markup=reply_markup)
    
    elif data.startswith("view_"):
        bot_name = data.split("view_")[1]
        bot_data = await bots_collection.find_one({"bot_name": bot_name, "admin_id": user_id})
        if bot_data:
            if user_id == bot_data["admin_id"]:
                buttons = [[InlineKeyboardButton("Settings", callback_data=f"settings_{bot_name}")]]
                await callback_query.edit_message_text(f"Bot: @{bot_name}\nYou are the admin.", reply_markup=InlineKeyboardMarkup(buttons))
    
    elif data.startswith("remove_"):
        bot_name = data.split("remove_")[1]
        bot_data = await bots_collection.find_one({"bot_name": bot_name, "admin_id": user_id})
        if bot_data:
            await bots_collection.delete_one({"bot_name": bot_name, "admin_id": user_id})
            token = bot_data["token"]
            if token in client.running_bots:
                await client.running_bots[token].stop()
                del client.running_bots[token]
            await callback_query.edit_message_text(f"Bot @{bot_name} removed successfully!")
    
    elif data.startswith("settings_"):
        bot_name = data.split("settings_")[1]
        buttons = [
            [InlineKeyboardButton("View Stats", callback_data=f"stats_{bot_name}")],
            [InlineKeyboardButton("Change Greeting", callback_data=f"greet_{bot_name}")],
            [InlineKeyboardButton("Back", callback_data="existing_bots")]
        ]
        await callback_query.edit_message_text(f"Settings for @{bot_name}:", reply_markup=InlineKeyboardMarkup(buttons))

# Handle token submission
@app.on_message(filters.text & filters.private)
async def handle_message(client, message):
    if hasattr(client, 'state') and client.state.get("awaiting_token") and client.state.get("user_id") == message.from_user.id:
        token = message.text.strip()
        try:
            # Verify token
            test_client = Client(
                f"bot_{token}",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=token
            )
            await test_client.start()
            bot_info = await test_client.get_me()
            await test_client.stop()
            
            # Check if bot already exists
            if await bots_collection.find_one({"bot_name": bot_info.username}):
                await message.reply_text(f"Bot @{bot_info.username} is already hosted!")
                del client.state
                return
            
            # Store bot in database
            bot_data = {
                "token": token,
                "bot_name": bot_info.username,
                "admin_id": message.from_user.id,
                "created_at": message.date
            }
            await bots_collection.insert_one(bot_data)
            
            # Start the hosted bot
            await start_hosted_bot(client, token, message.from_user.id)
            
            await message.reply_text(
                f"Bot @{bot_info.username} added successfully!\n"
                "Messages sent to this bot will be forwarded to you."
            )
            
        except Exception as e:
            await message.reply_text(f"Invalid token or error: {str(e)}")
        
        del client.state

async def start_hosted_bot(manager_client, token: str, admin_id: int):
    """Start a hosted bot instance"""
    hosted_bot = Client(
        f"bot_{token}",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=token,
        workers=50
    )
    
    await hosted_bot.start()
    me = await hosted_bot.get_me()
    hosted_bot.username = '@' + me.username  # Set username properly
    
    @hosted_bot.on_message(filters.private & ~filters.me)
    async def forward_message(client, message):
        forwarded = await message.forward(admin_id)
        manager_client.message_map[f"{admin_id}_{forwarded.id}"] = {
            "original_chat_id": message.chat.id,
            "original_message_id": message.id,
            "bot_token": token
        }
    
    @hosted_bot.on_message(filters.private & filters.user(admin_id))
    async def handle_admin_reply(client, message):
        if message.reply_to_message:
            reply_to_id = message.reply_to_message.id
            mapping_key = f"{admin_id}_{reply_to_id}"
            if mapping_key in manager_client.message_map:
                original_info = manager_client.message_map[mapping_key]
                await client.send_message(
                    original_info["original_chat_id"],
                    message.text,
                    reply_to_message_id=original_info["original_message_id"]
                )
    
    manager_client.running_bots[token] = hosted_bot
    print(f"Started hosted bot {hosted_bot.username}")

# Run the bot
if __name__ == "__main__":
    app.run()
