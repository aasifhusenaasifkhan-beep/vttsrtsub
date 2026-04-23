import os
import asyncio
import threading
import requests
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from http.server import HTTPServer, BaseHTTPRequestHandler

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("REPO_NAME") # Format: username/repo
PORT = 10000

# Security
OWNER_ID = int(os.getenv("OWNER_ID", "5351848105"))

app = Client("SubBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
users_data = {}

def trigger_github(task_payload):
    url = f"https://api.github.com/repos/{REPO_NAME}/actions/workflows/generate.yml/dispatches"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    payload = {"ref": "main", "inputs": task_payload}
    try:
        r = requests.post(url, headers=headers, json=payload)
        return r.status_code == 204, r.text
    except Exception as e:
        return False, str(e)

@app.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply("<b>🤖 Auto Subtitle Generator Bot</b>\n\n1. Video forward karo.\n2. Video pe reply karo `/vtt`, `/srt` ya `/ass`.\n3. English Sub banne ke baad, us file pe reply karo `/hienglish` hinglish ke liye.\n4. Bich me cancel karna ho to `/skip`.")

@app.on_message(filters.command("skip"))
async def cancel_task(client, message: Message):
    uid = message.from_user.id
    if uid in users_data:
        del users_data[uid]
        await message.reply("🛑 Task skipped in Bot Memory. (GitHub might still process in background but bot will ignore it)")
    else:
        await message.reply("❌ Koi active task nahi hai.")

# STEP 1: Video to English Subtitle
@app.on_message(filters.command(["vtt", "srt", "ass"]))
async def generate_sub(client, message: Message):
    format_type = message.command[0].lower()
    media = message.reply_to_message.video or message.reply_to_message.document if message.reply_to_message else None
    
    if not media: return await message.reply("❌ Please video/document pe reply karo.")
    
    status = await message.reply("⏳ Sending Video extraction task to GitHub...")
    
    task = {
        "task_type": "extract_english",
        "file_id": media.file_id,
        "format_type": format_type,
        "chat_id": str(message.chat.id),
        "msg_id": str(status.id)
    }
    
    users_data[message.from_user.id] = "processing"
    success, err = trigger_github(task)
    
    if success:
        await status.edit(f"✅ **GitHub Worker Started!**\nFormat: `.{format_type}`\nVideo se audio nikal kar Whisper English Subtitle bana raha hai. 10-15 min wait karein.")
    else:
        await status.edit(f"❌ **GitHub Trigger Failed:** {err}")

# STEP 2: English Subtitle to Hinglish (Roman Hindi)
@app.on_message(filters.command(["hienglish", "English"]))
async def translate_sub(client, message: Message):
    target_lang = message.command[0].lower()
    if target_lang == "english":
        return await message.reply("✅ Ye file already English me hai.")
        
    doc = message.reply_to_message.document if message.reply_to_message else None
    if not doc or not doc.file_name.endswith((".srt", ".vtt", ".ass")):
        return await message.reply("❌ Please generated Subtitle file (.srt, .vtt, .ass) pe reply karo.")
        
    status = await message.reply("⏳ Sending Translation task to GitHub...")
    
    task = {
        "task_type": "translate_hinglish",
        "file_id": doc.file_id,
        "format_type": doc.file_name.split('.')[-1],
        "chat_id": str(message.chat.id),
        "msg_id": str(status.id)
    }
    
    users_data[message.from_user.id] = "processing"
    success, err = trigger_github(task)
    
    if success:
        await status.edit("✅ **GitHub Worker Started!**\nEnglish Subtitles ko Hinglish me convert kiya ja raha hai... Timestamps same rahenge.")
    else:
        await status.edit(f"❌ **GitHub Trigger Failed:** {err}")

# Dummy Server for Render 24/7 Uptime
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Alive!")

async def main():
    await app.start()
    print("🤖 Bot Started Successfully!")
    await idle()

if __name__ == "__main__":
    threading.Thread(target=lambda: HTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever(), daemon=True).start()
    asyncio.get_event_loop().run_until_complete(main())
