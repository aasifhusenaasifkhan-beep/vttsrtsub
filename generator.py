import os
import sys
import time
import asyncio
import subprocess
import pysubs2
from pyrogram import Client
from faster_whisper import WhisperModel
from deep_translator import GoogleTranslator
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

import pyrogram.utils
def patched_get_peer_type(peer_id: int) -> str:
    val = str(peer_id)
    if val.startswith("-100"): return "channel"
    elif val.startswith("-"): return "chat"
    else: return "user"
pyrogram.utils.get_peer_type = patched_get_peer_type

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

TASK_TYPE = os.getenv("TASK_TYPE")
FILE_ID = os.getenv("FILE_ID")
FORMAT_TYPE = os.getenv("FORMAT_TYPE")
CHAT_ID = int(os.getenv("CHAT_ID"))
MSG_ID = int(os.getenv("MSG_ID"))

last_edit_time = 0

async def progress_bar(current, total, app, msg_id, action_text):
    global last_edit_time
    now = time.time()
    # Har 10 second me message edit hoga taaki Telegram flood limit na aaye
    if now - last_edit_time > 10 or current == total:
        try:
            percent = (current / total) * 100 if total > 0 else 0
            curr_mb = current / (1024 * 1024)
            tot_mb = total / (1024 * 1024) if total > 0 else 0
            await app.edit_message_text(CHAT_ID, msg_id, f"{action_text}\n⏳ `{percent:.1f}%` ({curr_mb:.1f}MB / {tot_mb:.1f}MB)")
            last_edit_time = now
        except:
            pass

async def edit_msg(app, text):
    try:
        await app.edit_message_text(CHAT_ID, MSG_ID, text)
    except:
        pass

async def download_file():
    app = Client("worker", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    await app.start()
    # Yahan progress bar add kar diya gaya hai
    file_path = await app.download_media(FILE_ID, progress=progress_bar, progress_args=(app, MSG_ID, "📥 GitHub: Downloading video..."))
    await app.stop()
    return file_path

async def upload_file(file_path, caption):
    app = Client("worker_up", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    await app.start()
    # Yahan bhi progress bar add kar diya gaya hai
    await app.send_document(CHAT_ID, document=file_path, caption=caption, reply_to_message_id=MSG_ID, progress=progress_bar, progress_args=(app, MSG_ID, "📤 GitHub: Uploading Final File..."))
    try:
        await app.delete_messages(CHAT_ID, MSG_ID)
    except:
        pass
    await app.stop()

def process_english(video_path):
    # Pehle audio extract karenge taaki AI tezi se process kare
    audio_path = "audio.wav"
    subprocess.run(["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio_path, "-y"], capture_output=True)
    
    # Whisper AI Run hoga (CPU optimized)
    model = WhisperModel("small", device="cpu", compute_type="int8")
    prompt = "This is a movie/anime. Translate accurately to English. Be mindful of correct gender pronouns."
    
    segments, info = model.transcribe(audio_path, task="translate", initial_prompt=prompt)
    
    subs = pysubs2.SSAFile()
    for segment in segments:
        event = pysubs2.SSAEvent(start=int(segment.start * 1000), end=int(segment.end * 1000), text=segment.text)
        subs.append(event)
    
    out_file = f"english_sub.{FORMAT_TYPE}"
    subs.save(out_file)
    
    # Cleanup memory
    os.remove(video_path)
    os.remove(audio_path)
    return out_file

def process_hinglish(sub_path):
    subs = pysubs2.load(sub_path)
    translator = GoogleTranslator(source='en', target='hi')
    
    for line in subs:
        if line.text.strip():
            hi_text = translator.translate(line.text)
            hinglish_text = transliterate(hi_text, sanscript.DEVANAGARI, sanscript.ITRANS)
            hinglish_text = hinglish_text.replace('aa', 'a').replace('ii', 'i').replace('uu', 'u').lower()
            line.text = hinglish_text.capitalize()
            
    out_file = f"hinglish_sub.{FORMAT_TYPE}"
    subs.save(out_file)
    os.remove(sub_path)
    return out_file

async def main():
    try:
        file_path = await download_file()
        
        # Download hone ke baad extraction status dikhayega
        app_status = Client("worker_status", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
        await app_status.start()
        
        if TASK_TYPE == "extract_english":
            await edit_msg(app_status, "⚙️ Extracting Audio & Generating Subtitles (Whisper AI)...\n*(Isme video ki length ke hisaab se 5-15 mins lag sakte hain)*")
            out_file = process_english(file_path)
            caption = f"✅ English Subtitle Generated\nFormat: `.{FORMAT_TYPE}`"
        
        elif TASK_TYPE == "translate_hinglish":
            await edit_msg(app_status, "⚙️ Translating to Hinglish...\n*(Timestamps match kiye jaa rahe hain)*")
            out_file = process_hinglish(file_path)
            caption = f"✅ Hinglish Subtitle Generated\nFormat: `.{FORMAT_TYPE}`"
            
        await app_status.stop()
        
        # Upload karega percentage ke sath
        await upload_file(out_file, caption)
        
        if os.path.exists(out_file):
            os.remove(out_file)
            
    except Exception as e:
        app = Client("worker_err", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
        await app.start()
        await edit_msg(app, f"❌ GitHub Error: {str(e)}")
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
