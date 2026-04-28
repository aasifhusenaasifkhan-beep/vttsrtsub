import os
import time
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

OWNER_ID = 5351848105       
ALLOWED_USERS = [5344078567]             
ALLOWED_GROUPS = [-1003899919015] 

app = Client("ManagerBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Variables
users_data = {}
UNAUTHORIZED_CAPTURED = set() 
BANNED_USERS = set()

BOT_BUSY = False
SLEEP_UNTIL = 0

edit = "Maintanence by: @Sub_and_hardsub"

def is_authorized(message: Message) -> bool:
    if not message.from_user: return False
    u_id = message.from_user.id    
    if u_id in BANNED_USERS: return False
    if u_id == OWNER_ID or u_id in ALLOWED_USERS or message.chat.id in ALLOWED_GROUPS:
        return True
    
    # Anjaan user ki ID save karega par reply kuch nahi karega (Ghost Mode)
    UNAUTHORIZED_CAPTURED.add(u_id)
    return False

def _send_to_github(task):
    url = f"https://api.github.com/repos/{REPO_NAME}/actions/workflows/encode.yml/dispatches"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    payload = {"ref": "main", "inputs": task}
    try:
        r = requests.post(url, headers=headers, json=payload)
        if r.status_code == 204:
            return True, "Success"
        else:
            return False, f"Code {r.status_code}: {r.text}"
    except Exception as e:
        return False, str(e)

async def trigger_github(task):
    return await asyncio.to_thread(_send_to_github, task)

# ================= ADMIN CONTROLS =================

@app.on_message(filters.command("add") & filters.user(OWNER_ID))
async def add_user(client, message: Message):
    try:
        new_id = int(message.command[1])
        if new_id not in ALLOWED_USERS:
            ALLOWED_USERS.append(new_id)
            if new_id in UNAUTHORIZED_CAPTURED:
                UNAUTHORIZED_CAPTURED.remove(new_id)
            await message.reply(f"✅ User `{new_id}` allowed.")
        else:
            await message.reply("⚠️ User already authorized.")
    except:
        await message.reply("❌ Use: `/add user_id`")

@app.on_message(filters.command("unauth") & filters.user(OWNER_ID))
async def show_unauth(client, message: Message):
    if not UNAUTHORIZED_CAPTURED:
        return await message.reply("No unauthorized attempts caught yet.")
    ids = "\n".join([f"`{uid}`" for uid in UNAUTHORIZED_CAPTURED])
    await message.reply(f"🚨 **Unauthorized Attempts:**\n{ids}\n\nUse `/add user_id` to allow them.")

@app.on_message(filters.command("sleep") & filters.user(OWNER_ID))
async def sleep_bot(client, message: Message):
    global SLEEP_UNTIL
    try:
        hours = float(message.command[1])
        SLEEP_UNTIL = time.time() + (hours * 3600)
        await message.reply(f"😴 Bot goes to sleep for {hours} hours. (Use /unsleep to wake up)")
    except:
        await message.reply("❌ Use: `/sleep 2`")

@app.on_message(filters.command("unsleep") & filters.user(OWNER_ID))
async def unsleep_bot(client, message: Message):
    global SLEEP_UNTIL
    SLEEP_UNTIL = 0
    await message.reply("☀️ Bot is awake and ready!")

@app.on_message(filters.command(["cancel", "remm"]))
async def cancel_task(client, message: Message):
    global BOT_BUSY
    if not is_authorized(message): return
    uid = message.from_user.id
    if uid in users_data:
        del users_data[uid]
    BOT_BUSY = False 
    await message.reply("🛑 Task memory cleared. Bot is now FREE.")

# ================= MAIN LOGIC =================

@app.on_message(filters.command("start"))
async def start(client, message: Message):
    if not is_authorized(message): return
    if time.time() < SLEEP_UNTIL: return
    await message.reply(f"<b>🔥 Hardsub bot (UltraFast + Compressed)</b>\n\n/hsub - Add subtitle\n/extracttrack - Extract Subtitle\n/cancel - Clear Memory\n/1080pdd, /720pdd, /480pdd - Resize\n\n{edit}")

@app.on_message(filters.command(["1080pdd", "720pdd", "480pdd"]))
async def resize_command(client, message: Message):
    global BOT_BUSY
    if not is_authorized(message): return
    if time.time() < SLEEP_UNTIL: return
    if BOT_BUSY: return await message.reply("❌ Bot is busy. Please wait or use /cancel.")

    target = message.command[0].replace("pdd", "")
    media = message.reply_to_message.video or message.reply_to_message.document if message.reply_to_message else None
    if not media: return await message.reply("❌ Reply to a video.")

    BOT_BUSY = True
    status = await message.reply(f"⏳ Sending {target}p Task to GitHub...")
    task = {"task_type": "resize", "video_id": media.file_id, "sub_id": "none", "wm_id": "none", "wm_pos": "none", "rename": f"resized_{target}p.mp4", "chat_id": str(message.chat.id), "resolution": target}
    
    success, err_msg = await trigger_github(task)
    if success: 
        await status.edit(f"✅ **Sent to GitHub!**\n*(Bot is now free to queue another task)*")
    else: 
        await status.edit(f"❌ **Trigger Failed!**\n`{err_msg}`")
    BOT_BUSY = False

@app.on_message(filters.command("extracttrack"))
async def extract_cmd(client, message: Message):
    global BOT_BUSY
    if not is_authorized(message): return
    if time.time() < SLEEP_UNTIL: return
    if BOT_BUSY: return await message.reply("❌ Bot is busy. Please wait or use /cancel.")

    media = message.reply_to_message.video or message.reply_to_message.document if message.reply_to_message else None
    if not media: return await message.reply("❌ Reply to a video.")

    BOT_BUSY = True
    status = await message.reply("⏳ Sending Extract Task to GitHub...")
    task = {"task_type": "extract", "video_id": media.file_id, "sub_id": "none", "wm_id": "none", "wm_pos": "none", "rename": "extracted_sub.srt", "chat_id": str(message.chat.id), "resolution": "none"}
    
    success, err_msg = await trigger_github(task)
    if success: 
        await status.edit("✅ **Sent to GitHub! Extracting Subtitle...**\n*(Bot is now free)*")
    else: 
        await status.edit(f"❌ **Trigger Failed!**\n`{err_msg}`")
    BOT_BUSY = False

@app.on_message(filters.command("hsub"))
async def hsub_cmd(client, message: Message):
    global BOT_BUSY
    if not is_authorized(message): return
    if time.time() < SLEEP_UNTIL: return
    if BOT_BUSY: return await message.reply("❌ Bot is busy. Please wait or use /cancel.")

    media = message.reply_to_message.video or message.reply_to_message.document if message.reply_to_message else None
    if not media: return await message.reply("❌ Reply to a video.")
    
    BOT_BUSY = True
    users_data[message.from_user.id] = {"video_id": media.file_id, "chat_id": str(message.chat.id), "state": "WAIT_SUB", "file_name": media.file_name or "video.mp4"}
    await message.reply("📄 Send Subtitle (.srt/.ass)", reply_to_message_id=message.id)

@app.on_message(filters.document | filters.video | filters.photo | filters.text)
async def handle_inputs(client, message: Message):
    if not is_authorized(message): return
    if time.time() < SLEEP_UNTIL: return
    uid = message.from_user.id
    if uid not in users_data: return
    state = users_data[uid].get("state")
    
    if state == "WAIT_SUB" and message.document and message.document.file_name.endswith((".srt", ".ass")):
        users_data[uid]["sub_id"] = message.document.file_id
        users_data[uid]["state"] = "WAIT_WM_CHOICE"
        await message.reply("Add Watermark?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Yes", callback_data="wm_yes"), InlineKeyboardButton("No", callback_data="wm_skip")]]), reply_to_message_id=message.id)
    
    elif state == "WAIT_WM_PIC" and message.photo:
        users_data[uid]["wm_id"] = message.photo.file_id
        users_data[uid]["state"] = "WAIT_WM_POS"
        await message.reply("Position:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Top-Left", callback_data="pos_TL"), InlineKeyboardButton("Top-Right", callback_data="pos_TR")]]), reply_to_message_id=message.id)
    
    elif state == "WAIT_RENAME_TEXT" and message.text:
        users_data[uid]["file_name"] = message.text.strip() + ".mp4" if not message.text.endswith(".mp4") else message.text.strip()
        await send_to_queue(uid, message)

@app.on_callback_query()
async def callbacks(client, query: CallbackQuery):
    uid = query.from_user.id
    if uid not in users_data: return await query.answer("No active task!", show_alert=True)
    d = query.data
    
    if d == "wm_yes":
        users_data[uid]["state"] = "WAIT_WM_PIC"
        await query.message.edit("🖼️ Send Photo for Watermark.")
    elif d == "wm_skip":
        users_data[uid]["wm_id"] = "none"
        users_data[uid]["wm_pos"] = "none"
        users_data[uid]["state"] = "WAIT_RENAME_CHOICE"
        await ask_rename(query.message)
    elif d.startswith("pos_"):
        users_data[uid]["wm_pos"] = "TL" if d == "pos_TL" else "TR"
        users_data[uid]["state"] = "WAIT_RENAME_CHOICE"
        await ask_rename(query.message)
    elif d == "rn_yes":
        users_data[uid]["state"] = "WAIT_RENAME_TEXT"
        await query.message.edit("📝 Send new file name.")
    elif d == "rn_skip":
        await send_to_queue(uid, query.message)

async def ask_rename(msg):
    await msg.edit("Rename file?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Yes", callback_data="rn_yes"), InlineKeyboardButton("Skip", callback_data="rn_skip")]]))

async def send_to_queue(uid, msg):
    global BOT_BUSY
    d = users_data.pop(uid)
    task = {
        "task_type": "hsub",
        "video_id": d["video_id"],
        "sub_id": d.get("sub_id", "none"),
        "wm_id": d.get("wm_id", "none"),
        "wm_pos": d.get("wm_pos", "none"),
        "rename": d.get("file_name", "output.mp4"),
        "chat_id": d["chat_id"],
        "resolution": "none"
    }
    status = await msg.reply("⏳ Sending Task to GitHub...")
    success, err_msg = await trigger_github(task)
    if success: 
        await status.edit("✅ **Sent to GitHub! Process started.**")
    else: 
        await status.edit(f"❌ **Trigger Failed!**\nGitHub said: `{err_msg}`")
    BOT_BUSY = False

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Running")

async def main():
    if edit != "Maintanence by: @Sub_and_hardsub": return
    await app.start()
    print("Bot started: Anti-Sleep & Ghost Mode Enabled.")
    await idle()

if __name__ == "__main__":
    threading.Thread(target=lambda: HTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever(), daemon=True).start()
    asyncio.get_event_loop().run_until_complete(main())
