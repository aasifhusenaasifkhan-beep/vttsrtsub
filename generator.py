import os
import sys
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

async def edit_msg(app, text):
    try:
        await app.edit_message_text(CHAT_ID, MSG_ID, text)
    except:
        pass

async def download_file():
    app = Client("worker", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    await app.start()
    await edit_msg(app, "📥 GitHub: Downloading file...")
    file_path = await app.download_media(FILE_ID)
    await app.stop()
    return file_path

async def upload_file(file_path, caption):
    app = Client("worker_up", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    await app.start()
    await edit_msg(app, "📤 GitHub: Uploading Final File...")
    await app.send_document(CHAT_ID, document=file_path, caption=caption, reply_to_message_id=MSG_ID)
    await app.delete_messages(CHAT_ID, MSG_ID)
    await app.stop()

def process_english(video_path):
    # Extract audio for faster processing
    audio_path = "audio.wav"
    subprocess.run(["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio_path, "-y"], capture_output=True)
    
    # Run Faster-Whisper
    # CPU par best speed ke liye 'small' ya 'base' model use karte hai
    model = WhisperModel("small", device="cpu", compute_type="int8")
    
    # Prompt to avoid gender mistakes and keep it context accurate
    prompt = "This is a movie/anime. Translate accurately to English. Be mindful of correct gender pronouns."
    
    segments, info = model.transcribe(audio_path, task="translate", initial_prompt=prompt)
    
    subs = pysubs2.SSAFile()
    for segment in segments:
        event = pysubs2.SSAEvent(start=int(segment.start * 1000), end=int(segment.end * 1000), text=segment.text)
        subs.append(event)
    
    out_file = f"english_sub.{FORMAT_TYPE}"
    subs.save(out_file)
    
    # Cleanup
    os.remove(video_path)
    os.remove(audio_path)
    return out_file

def process_hinglish(sub_path):
    subs = pysubs2.load(sub_path)
    translator = GoogleTranslator(source='en', target='hi')
    
    for line in subs:
        if line.text.strip():
            # 1. Translate to Devanagari Hindi
            hi_text = translator.translate(line.text)
            # 2. Transliterate to Roman (Hinglish like format)
            # We use ITRANS and convert it to lowercase for natural Hinglish reading
            hinglish_text = transliterate(hi_text, sanscript.DEVANAGARI, sanscript.ITRANS)
            # Basic cleanup for ITRANS outputs
            hinglish_text = hinglish_text.replace('aa', 'a').replace('ii', 'i').replace('uu', 'u').lower()
            line.text = hinglish_text.capitalize()
            
    out_file = f"hinglish_sub.{FORMAT_TYPE}"
    subs.save(out_file)
    os.remove(sub_path)
    return out_file

async def main():
    try:
        file_path = await download_file()
        
        if TASK_TYPE == "extract_english":
            out_file = process_english(file_path)
            caption = f"✅ English Subtitle Generated\nFormat: `.{FORMAT_TYPE}`"
        
        elif TASK_TYPE == "translate_hinglish":
            out_file = process_hinglish(file_path)
            caption = f"✅ Hinglish Subtitle Generated\nFormat: `.{FORMAT_TYPE}`"
            
        await upload_file(out_file, caption)
        os.remove(out_file) # Final cleanup
        
    except Exception as e:
        app = Client("worker_err", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
        await app.start()
        await edit_msg(app, f"❌ GitHub Error: {str(e)}")
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
