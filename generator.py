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

# Pyrogram पैच (Group/Channel issue fix)
import pyrogram.utils
def patched_get_peer_type(peer_id: int) -> str:
    val = str(peer_id)
    if val.startswith("-100"): return "channel"
    elif val.startswith("-"): return "chat"
    else: return "user"
pyrogram.utils.get_peer_type = patched_get_peer_type

# Environment Variables
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

TASK_TYPE = os.getenv("TASK_TYPE")
FILE_ID = os.getenv("FILE_ID")
FORMAT_TYPE = os.getenv("FORMAT_TYPE")
CHAT_ID = int(os.getenv("CHAT_ID"))
MSG_ID = int(os.getenv("MSG_ID"))

app = None
last_edit_time = 0

async def edit_msg(text):
    """मैसेज एडिट करने का हेल्पर फंक्शन"""
    try:
        await app.edit_message_text(CHAT_ID, MSG_ID, text)
    except Exception:
        pass

async def progress_bar(current, total, action_text):
    """Live Progress dekhne ke liye taaki bot mara hua na lage"""
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
    # ऑडियो निकालें (तेजी के लिए)
    audio_path = "audio.wav"
    subprocess.run([
        "ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1", audio_path, "-y"
    ], capture_output=True)

    # 🔧 'small' model - Japanese/Korean/Chinese translation ke liye ye zaroori hai. base fail ho jata hai.
    model = WhisperModel("small", device="cpu", compute_type="int8")

    # 🔧 Settings to fix Hallucination & Timing 
    segments, info = model.transcribe(
        audio_path,
        task="translate",            # Kisi bhi language ko automatically English me karega
        vad_filter=True,             # Silence hatakar Timing sahi karega
        vad_parameters=dict(min_silence_duration_ms=500),
        condition_on_previous_text=False,  # 🔥 YAHI HAI MAGIC! Isse AI line repeat nahi karega
        beam_size=5,
        initial_prompt=None          # Prompt hata diya taaki wo subtitles me na chhape
    )

    subs = pysubs2.SSAFile()
    for segment in segments:
        text = segment.text.strip()
        
        # Faltu choti lines ya kachra hatane ke liye filter
        if not text or len(text) < 2:
            continue
            
        event = pysubs2.SSAEvent(
            start=int(segment.start * 1000),
            end=int(segment.end * 1000),
            text=text
        )
        subs.append(event)

    out_file = f"english_sub.{FORMAT_TYPE}"
    subs.save(out_file)

    # सफाई
    os.remove(video_path)
    os.remove(audio_path)
    return out_file

def process_hinglish(sub_path):
    subs = pysubs2.load(sub_path)
    translator = GoogleTranslator(source='en', target='hi')

    for line in subs:
        if line.text.strip():
            try:
                # 1. Hindi Me translate
                hi_text = translator.translate(line.text)
                # 2. Hinglish (Roman) me convert
                hinglish_text = transliterate(hi_text, sanscript.DEVANAGARI, sanscript.ITRANS)
                hinglish_text = hinglish_text.replace('aa', 'a').replace('ii', 'i').replace('uu', 'u').lower()
                line.text = hinglish_text.capitalize()
            except Exception:
                continue # Agar koi error aaye toh line skip kardo bot crash na ho

    out_file = f"hinglish_sub.{FORMAT_TYPE}"
    subs.save(out_file)
    os.remove(sub_path)
    return out_file

async def main():
    global app
    # 🌟 in_memory=True rakha hai taaki GitHub action par session crash na ho!
    app = Client(
        "worker_session",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True  
    )

    try:
        await app.start()
        file_path = await download_file()

        if TASK_TYPE == "extract_english":
            await edit_msg("⚙️ Extracting Audio & Translating to English...\n*(AI dialogue sync kar raha hai...)*")
            # Run Whisper Model
            loop = asyncio.get_event_loop()
            out_file = await loop.run_in_executor(None, process_english, file_path)
            caption = f"✅ English Subtitle Generated\nFormat: `.{FORMAT_TYPE}`"

        elif TASK_TYPE == "translate_hinglish":
            await edit_msg("⚙️ Translating Subtitles to Hinglish...\n*(Timestamps lock kiye jaa rahe hain...)*")
            # Run Hinglish Logic
            loop = asyncio.get_event_loop()
            out_file = await loop.run_in_executor(None, process_hinglish, file_path)
            caption = f"✅ Hinglish Subtitle Generated\nFormat: `.{FORMAT_TYPE}`"

        await upload_file(out_file, caption)
        
        if os.path.exists(out_file):
            os.remove(out_file)

    except Exception as e:
        await edit_msg(f"❌ GitHub Error: {str(e)}")
    finally:
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
