import os
import sys
import time
import asyncio
import subprocess
import pysubs2
import re
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
STYLE_TYPE = os.getenv("STYLE_TYPE", "normal")

app = None
last_edit_time = 0

async def edit_msg(text):
    try: await app.edit_message_text(CHAT_ID, MSG_ID, text)
    except Exception: pass

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
        except: pass

async def download_file():
    await edit_msg("📥 GitHub: Downloading file...")
    return await app.download_media(FILE_ID, progress=progress_bar, progress_args=("📥 Downloading...",))

async def upload_file(file_path, caption):
    await edit_msg("📤 GitHub: Uploading Final Subtitle...")
    await app.send_document(CHAT_ID, document=file_path, caption=caption, reply_to_message_id=MSG_ID)
    try: await app.delete_messages(CHAT_ID, MSG_ID)
    except: pass

# --- ASI CUSTOM ASS FORMATTER ---
def apply_asi_style(file_path):
    subs = pysubs2.load(file_path)
    if len(subs) == 0: return

    # Find the end time of the very last dialogue
    max_end_ms = max(line.end for line in subs)
    
    def ms_to_time(ms):
        h, m, s, cs = ms // 3600000, (ms % 3600000) // 60000, (ms % 60000) // 1000, (ms % 1000) // 10
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    max_time_str = ms_to_time(max_end_ms)

    # EXACT Format Provide by User
    ass_content = f"""[Script Info]
Title: ASI ASS Script - Complete & Fixed
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1920
PlayResY: 1080
YCbCr Matrix: TV.601

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ASI ᴀɴɪᴍᴇ_Watermark,Arial,140,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,5,2,9,10,40,40,1
Style: Default,Arial,90,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,-1,0,0,100,100,0,0,1,3.8,2,2,100,100,58,1
Style: Logo,Arial,30,&H00FFFFFF,&H00FFFFFF,&H000000FF,&H96000000,0,0,0,0,100,100,0,0,1,3,0,2,10,35,0.8,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
; Watermark
Dialogue: 10,0:00:00.00,{max_time_str},ASI ᴀɴɪᴍᴇ_Watermark,,0000,0000,0000,,{{\\bord8\\blur5\\shad3}} {{\\c&HFF00FF&}}𝙰{{\\c&HFFFFFF&}}𝚂{{\\c&H00A0FF&}}𝙸☠

; Main Subtitles
"""
    for line in subs:
        start_t = ms_to_time(line.start)
        end_t = ms_to_time(line.end)
        text = line.text.replace('\n', '\\N')
        ass_content += f"Dialogue: 0,{start_t},{end_t},Default,,0000,0000,0000,,{text}\n"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

def clean_text(text):
    """Gande characters hatane ka filter"""
    return re.sub(r'[<>/\\]', '', text).strip()

def process_english(video_path):
    audio_path = "audio.wav"
    subprocess.run(["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio_path, "-y"], capture_output=True)

    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        audio_path, task="translate", vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500),
        condition_on_previous_text=False, beam_size=5,
        initial_prompt="Translate accurately to English."
    )

    subs = pysubs2.SSAFile()
    for segment in segments:
        text = clean_text(segment.text)
        if not text or len(text) < 2: continue
        subs.append(pysubs2.SSAEvent(start=int(segment.start * 1000), end=int(segment.end * 1000), text=text))

    out_file = f"{FILE_NAME}.{FORMAT_TYPE}"
    subs.save(out_file)

    if FORMAT_TYPE == "ass" and STYLE_TYPE == "asi_style":
        apply_asi_style(out_file)

    os.remove(video_path)
    os.remove(audio_path)
    return out_file

def clean_whatsapp_hinglish(hindi_text):
    """WhatsApp Hindi chatting style ko natural banata hai"""
    roman = unidecode(hindi_text).lower()
    
    # Text ko theek karna
    replacements = {
        "main ": "me ", " hun": " hu", " hain": " hai", " thaa": " tha", " thii": " thi",
        " mujhko ": " muje ", " tujhko ": " tuje ", " kyaa": " kya", " jaa ": " ja "
    }
    for old, new in replacements.items():
        roman = roman.replace(old, new)
        
    return clean_text(roman.capitalize())

def process_hinglish(sub_path):
    subs = pysubs2.load(sub_path)
    translator = GoogleTranslator(source='en', target='hi')
    
    texts_to_translate = []
    valid_indices = []
    
    for i, line in enumerate(subs):
        clean_line = clean_text(line.text)
        if clean_line:
            texts_to_translate.append(clean_line)
            valid_indices.append(i)

    if texts_to_translate:
        try:
            hi_translations = translator.translate_batch(texts_to_translate)
            for idx, hi_text in zip(valid_indices, hi_translations):
                if hi_text:
                    final_text = clean_whatsapp_hinglish(hi_text)
                    subs[idx].text = final_text
        except Exception as e:
            print("Translation error:", e)

    out_file = f"{FILE_NAME}_Hinglish.{FORMAT_TYPE}"
    subs.save(out_file)

    if FORMAT_TYPE == "ass" and STYLE_TYPE == "asi_style":
        apply_asi_style(out_file)

    os.remove(sub_path)
    return out_file

async def main():
    global app
    app = Client("worker_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

    try:
        await app.start()
        file_path = await download_file()
        loop = asyncio.get_event_loop()

        if TASK_TYPE == "extract_english":
            await edit_msg(f"⚙️ Generating English Subtitle...\n*(File: {FILE_NAME} | Style: {STYLE_TYPE})*")
            out_file = await loop.run_in_executor(None, process_english, file_path)
            caption = f"✅ English Subtitle Generated\nFile: `{FILE_NAME}.{FORMAT_TYPE}`"

        elif TASK_TYPE == "translate_hinglish":
            await edit_msg(f"⚡ Fast Translating to Hinglish...\n*(File: {FILE_NAME} | Style: {STYLE_TYPE})*")
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
