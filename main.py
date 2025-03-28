from pyrogram import Client
import aiohttp
from config import API_ID, API_HASH, BOT_TOKEN

# API endpoint details
RAPIDAPI_HOST = "terabox-downloader-online-viewer-player-api.p.rapidapi.com"
RAPIDAPI_KEY = "40f2e82091mshde814f0686f92ffp1833b5jsn9c8efed709fb"
API_URL = "https://terabox-downloader-online-viewer-player-api.p.rapidapi.com/rapidapi"

class Bot(Client):
    def __init__(self):
        super().__init__(
            "vj string session bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins=dict(root="TechVJ"),
            workers=150,
            sleep_threshold=10
        )
        
    async def start(self):           
        await super().start()
        me = await self.get_me()
        self.username = '@' + me.username          
        print('Bot Started Powered By @VJ_Botz')

    async def stop(self, *args):
        await super().stop()
        print('Bot Stopped Bye')
    
    # Command handler for /start
    async def on_message(self, message):
        if message.text and message.text.startswith('/start'):
            await message.reply_text("Hello! I'm a Terabox API bot. Send me /getdata to fetch Terabox API data.")
            
        elif message.text and message.text.startswith('/getdata'):
            try:
                # API configuration for RapidAPI
                headers = {
                    "X-RapidAPI-Key": RAPIDAPI_KEY,
                    "X-RapidAPI-Host": RAPIDAPI_HOST
                }
                
                # Make API request
                async with aiohttp.ClientSession() as session:
                    async with session.get(API_URL, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            # Format the response
                            response_text = "Terabox API Response:\n\n"
                            response_text += f"```json\n{str(data)}\n```"
                            await message.reply_text(response_text)
                        else:
                            await message.reply_text(f"Error: API request failed with status {response.status}")
            except Exception as e:
                await message.reply_text(f"Error occurred: {str(e)}")

if __name__ == "__main__":
    Bot().run()
