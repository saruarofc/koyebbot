import aiohttp
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN
import json
import base64
import random

# bKash API credentials (Use sandbox credentials)
BKASH_USERNAME = "your_bkash_username"
BKASH_PASSWORD = "your_bkash_password"
BKASH_APP_KEY = "your_app_key"
BKASH_APP_SECRET = "your_app_secret"

# bKash sandbox API URLs (Bkash)
BKASH_API_BASE = "https://tokenized.sandbox.bka.sh/v1.2.0-beta/tokenized/checkout"
CREATE_PAYMENT_URL = f"{BKASH_API_BASE}/create"
EXECUTE_PAYMENT_URL = f"{BKASH_API_BASE}/execute"

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
            await message.reply_text("Hello! I'm a bKash Payment bot. Use /pay to make payments.")
        
        elif message.text and message.text.startswith('/pay'):
            await message.reply_text("Please send your bKash number to make the payment.")
            self.state = "waiting_for_bkash_number"
        
        elif self.state == "waiting_for_bkash_number":
            self.bkash_number = message.text
            await message.reply_text(f"Got it! Now please send the amount to pay.")
            self.state = "waiting_for_amount"
        
        elif self.state == "waiting_for_amount":
            self.amount = message.text
            await message.reply_text(f"Amount set: {self.amount}. Now I'll initiate the payment.")
            await self.create_payment(message)
            self.state = None

    async def create_payment(self, message):
        # Set the headers for authentication
        headers = {
            "Authorization": f"Basic {base64.b64encode(f'{BKASH_APP_KEY}:{BKASH_APP_SECRET}'.encode()).decode()}",
            "Content-Type": "application/json"
        }

        # Payment request payload
        payment_data = {
            "amount": self.amount,
            "payerReference": self.bkash_number,
            "merchantCode": "your_merchant_code",  # Replace with your merchant code
            "currency": "BDT"
        }

        # Create the payment using bKash sandbox API
        async with aiohttp.ClientSession() as session:
            async with session.post(CREATE_PAYMENT_URL, json=payment_data, headers=headers) as response:
                if response.status == 200:
                    response_json = await response.json()
                    # Send the actual Create Payment response from bKash to the user
                    await message.reply_text(f"Payment Created! Here's the response:\n\n```json\n{json.dumps(response_json, indent=4)}\n```")
                    # After payment creation, execute the payment
                    await self.execute_payment(message, response_json['paymentID'])
                else:
                    await message.reply_text(f"Error: Could not create payment. Status code: {response.status}")

    async def execute_payment(self, message, payment_id):
        # Set the headers for authentication
        headers = {
            "Authorization": f"Basic {base64.b64encode(f'{BKASH_APP_KEY}:{BKASH_APP_SECRET}'.encode()).decode()}",
            "Content-Type": "application/json"
        }

        # Payment execution request payload
        payment_execution_data = {
            "paymentID": payment_id,
            "otp": "123456"  # Here you will need to replace with the OTP received from bKash for verification
        }

        # Execute the payment using bKash sandbox API
        async with aiohttp.ClientSession() as session:
            async with session.post(EXECUTE_PAYMENT_URL, json=payment_execution_data, headers=headers) as response:
                if response.status == 200:
                    response_json = await response.json()
                    # Send the actual Execute Payment response from bKash to the user
                    await message.reply_text(f"Payment Executed! Here's the response:\n\n```json\n{json.dumps(response_json, indent=4)}\n```")
                else:
                    await message.reply_text(f"Error: Could not execute payment. Status code: {response.status}")

if __name__ == "__main__":
    Bot().run()
