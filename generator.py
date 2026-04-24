import os
import sys
import time
import asyncio
import subprocess
import pysubs2
from pyrogram import Client
from faster_whisper import WhisperModel
from deep_translator import GoogleTranslator
from unidecode import unidecode

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
FILE_NAME = os.getenv("FILE_NAME", "subtitle")

app = None
last_edit_time = 0

async def edit_msg(text):
    try:
        await app.edit_message_text(CHAT_ID, MSG_ID, text)
    except Exception:
        pass

async def progress_bar(current, total, action_text):
    global last_edit_time
    now = time.time()
    if now - last_edit_time > 10 or current == total:
        try:
            percent = (current / total) * 100 if total > 0 else 0
            curr_mb = current / (1024 * 1024)
            tot_mb = total / (1024 * 1024) if total > 0 else 0
            await edit_msg(f"{action_text}\n⏳ `{percent:.1f}%` ({curr_mb:.1f}MB / {tot_mb:.1f}MB)")
            last_edit_time = now
        except:
            pass

async def download_file():
    await edit_msg("📥 GitHub: Downloading video...")
    file_path = await app.download_media(FILE_ID, progress=progress_bar, progress_args=("📥 Downloading...",))
    return file_path

async def upload_file(file_path, caption):
    await edit_msg("📤 GitHub: Uploading Final Subtitle...")
    await app.send_document(CHAT_ID, document=file_path, caption=caption, reply_to_message_id=MSG_ID)
    try:
        await app.delete_messages(CHAT_ID, MSG_ID)
    except:
        pass

def process_english(video_path):
    audio_path = "audio.wav"
    subprocess.run(["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio_path, "-y"], capture_output=True)

    model = WhisperModel("small", device="cpu", compute_type="int8")

    segments, info = model.transcribe(
        audio_path,
        task="translate",
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
        condition_on_previous_text=False,
        beam_size=5,
        initial_prompt="Translate the Japanese/Korean accurately to English. Pay close attention to male/female speech context."
    )

    subs = pysubs2.SSAFile()
    for segment in segments:
        text = segment.text.strip()
        if not text or len(text) < 2:
            continue
        event = pysubs2.SSAEvent(start=int(segment.start * 1000), end=int(segment.end * 1000), text=text)
        subs.append(event)

    out_file = f"{FILE_NAME}.{FORMAT_TYPE}"
    subs.save(out_file)

    os.remove(video_path)
    os.remove(audio_path)
    return out_file

def clean_whatsapp_hinglish(hindi_text):
    """Hindi ko perfect WhatsApp chatting wali Hinglish me badalta hai"""
    # Sanskrit rules ke bina direct Roman me convert karega
    roman = unidecode(hindi_text).lower()

    # Chhoti si safai (Cleanup) taaki padhne me natural lage
    replacements = {
        "main ": "me ",
        " hun": " hu",
        " hain": " hai",
        " kyaa": " kya",
        "thaa": "tha",
        "thii": "thi",
        "jaa": "ja",
        "aao": "aao",
        "rahaa": "raha",
        "rahii": "rahi",
        "jahu": "jau"
    }
    
    for old, new in replacements.items():
        roman = roman.replace(old, new)
        
    return roman.capitalize()

def process_hinglish(sub_path):
    subs = pysubs2.load(sub_path)
    translator = GoogleTranslator(source='en', target='hi')
    
    # BATCH TRANSLATION (SPEED FAST RAKHNE KE LIYE)
    texts_to_translate = []
    valid_indices = []
    
    for i, line in enumerate(subs):
        if line.text.strip():
            texts_to_translate.append(line.text.strip())
            valid_indices.append(i)

    if texts_to_translate:
        try:
            # Pura batch ek sath Devanagari (Hindi) me translate hoga
            hi_translations = translator.translate_batch(texts_to_translate)
            
            for idx, hi_text in zip(valid_indices, hi_translations):
                if hi_text:
                    # Hindi ko perfect Hinglish me convert karega
                    final_text = clean_whatsapp_hinglish(hi_text)
                    subs[idx].text = final_text
        except Exception as e:
            print("Translation error:", e)

    out_file = f"{FILE_NAME}_Hinglish.{FORMAT_TYPE}"
    subs.save(out_file)
    os.remove(sub_path)
    return out_file

async def main():
    global app
    app = Client("worker_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

    try:
        await app.start()
        file_path = await download_file()

        if TASK_TYPE == "extract_english":
            await edit_msg(f"⚙️ Generating English Subtitle...\n*(File: {FILE_NAME})*")
            loop = asyncio.get_event_loop()
            out_file = await loop.run_in_executor(None, process_english, file_path)
            caption = f"✅ English Subtitle Generated\nFile: `{FILE_NAME}.{FORMAT_TYPE}`"

        elif TASK_TYPE == "translate_hinglish":
            await edit_msg(f"⚡ Fast Translating to Hinglish...\n*(File: {FILE_NAME})*")
            loop = asyncio.get_event_loop()
            out_file = await loop.run_in_executor(None, process_hinglish, file_path)
            caption = f"✅ Hinglish Subtitle Generated\nFile: `{FILE_NAME}_Hinglish.{FORMAT_TYPE}`"

        await upload_file(out_file, caption)
        if os.path.exists(out_file): os.remove(out_file)

    except Exception as e:
        await edit_msg(f"❌ Error: {str(e)}")
    finally:
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
