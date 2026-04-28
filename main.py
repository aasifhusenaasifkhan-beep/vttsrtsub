import os
import asyncio
import threading
import requests
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from http.server import HTTPServer, BaseHTTPRequestHandler

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("REPO_NAME")
PORT = 10000

app = Client("SubBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
users_data = {}

def _send_trigger(task_payload):
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

async def trigger_github(task_payload):
    return await asyncio.to_thread(_send_trigger, task_payload)

@app.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply("<b>🤖 Auto Subtitle Generator Bot</b>\n\nQueue System Active. Send Video -> Reply `/vtt`, `/srt`, `/ass`.")

@app.on_message(filters.command("skip"))
async def cancel_task(client, message: Message):
    uid = message.from_user.id
    if uid in users_data:
        del users_data[uid]
        await message.reply("🛑 Task skipped in Bot Memory.")
    else:
        await message.reply("❌ Koi active task nahi hai.")

@app.on_message(filters.command(["vtt", "srt", "ass"]))
async def generate_sub(client, message: Message):
    format_type = message.command[0].lower()
    media = message.reply_to_message.video or message.reply_to_message.document if message.reply_to_message else None
    
    if not media: return await message.reply("❌ Please video/document pe reply karo.")
    
    original_name = getattr(media, "file_name", "video.mp4")
    if not original_name: original_name = "video.mp4"
    base_name = original_name.rsplit(".", 1)[0]
    
    # ASS file ke liye Style poochne ka option
    if format_type == "ass":
        users_data[message.from_user.id] = {
            "task_type": "extract_english", "file_id": media.file_id, 
            "format_type": "ass", "chat_id": str(message.chat.id), "file_name": base_name
        }
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎨 ASI Style + Watermark", callback_data="style_asi")],
            [InlineKeyboardButton("📄 Normal Direct Style", callback_data="style_normal")]
        ])
        await message.reply("❓ **Kaunsa Style lagana hai?**", reply_markup=keyboard)
        return

    status = await message.reply("⏳ Sending Task to GitHub Queue...")
    task = {"task_type": "extract_english", "file_id": media.file_id, "format_type": format_type, "chat_id": str(message.chat.id), "msg_id": str(status.id), "file_name": base_name, "style_type": "normal"}
    
    success, err = await trigger_github(task)
    if success: await status.edit(f"✅ **Task Added to Queue!**\nName: `{base_name}`\nFormat: `.{format_type}`")
    else: await status.edit(f"❌ **Trigger Failed:** {err}")

@app.on_message(filters.command(["hienglish", "English"]))
async def translate_sub(client, message: Message):
    target_lang = message.command[0].lower()
    if target_lang == "english": return await message.reply("✅ Ye file already English me hai.")
        
    doc = message.reply_to_message.document if message.reply_to_message else None
    if not doc or not doc.file_name.endswith((".srt", ".vtt", ".ass")): return await message.reply("❌ Please generated Subtitle file pe reply karo.")
        
    base_name = doc.file_name.rsplit(".", 1)[0]
    format_type = doc.file_name.split('.')[-1]
    
    if format_type == "ass":
        users_data[message.from_user.id] = {
            "task_type": "translate_hinglish", "file_id": doc.file_id, 
            "format_type": "ass", "chat_id": str(message.chat.id), "file_name": base_name
        }
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎨 ASI Style + Watermark", callback_data="style_asi")],
            [InlineKeyboardButton("📄 Normal Direct Style", callback_data="style_normal")]
        ])
        await message.reply("❓ **Kaunsa Style lagana hai?**", reply_markup=keyboard)
        return

    status = await message.reply("⏳ Sending Translation to GitHub Queue...")
    task = {"task_type": "translate_hinglish", "file_id": doc.file_id, "format_type": format_type, "chat_id": str(message.chat.id), "msg_id": str(status.id), "file_name": base_name, "style_type": "normal"}
    
    success, err = await trigger_github(task)
    if success: await status.edit("✅ **Added to Queue!**\nBatch Translating to Hinglish...")
    else: await status.edit(f"❌ **Trigger Failed:** {err}")

@app.on_callback_query(filters.regex("^style_"))
async def handle_style_selection(client, callback_query: CallbackQuery):
    uid = callback_query.from_user.id
    if uid not in users_data: return await callback_query.answer("No active task!", show_alert=True)
    
    style_choice = "asi_style" if callback_query.data == "style_asi" else "normal"
    d = users_data.pop(uid)
    
    await callback_query.message.edit_text("⏳ Sending Task to GitHub Queue with selected style...")
    
    task = {
        "task_type": d["task_type"],
        "file_id": d["file_id"],
        "format_type": d["format_type"],
        "chat_id": d["chat_id"],
        "msg_id": str(callback_query.message.id),
        "file_name": d["file_name"],
        "style_type": style_choice
    }
    
    success, err = await trigger_github(task)
    if success: await callback_query.message.edit_text(f"✅ **Task Added to Queue!**\nStyle: `{style_choice}`")
    else: await callback_query.message.edit_text(f"❌ **Trigger Failed:** {err}")

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"Bot is Alive!")

async def keep_alive():
    while True:
        await asyncio.sleep(5 * 60)
        try: requests.get("http://localhost:10000")
        except: pass

async def main():
    await app.start()
    print("🤖 Bot Started Successfully!")
    asyncio.create_task(keep_alive())
    await idle()

if __name__ == "__main__":
    threading.Thread(target=lambda: HTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever(), daemon=True).start()
    asyncio.get_event_loop().run_until_complete(main())
