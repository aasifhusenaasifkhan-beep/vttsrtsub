import os, sys, time, asyncio, subprocess, pyrogram.utils
from pyrogram import Client

pyrogram.utils.get_peer_type = lambda p: "channel" if str(p).startswith("-100") else "chat" if str(p).startswith("-") else "user"

API_ID, API_HASH, BOT_TOKEN = int(os.getenv("API_ID")), os.getenv("API_HASH"), os.getenv("BOT_TOKEN")
TASK_TYPE, VIDEO_ID, SUB_ID = os.getenv("TASK_TYPE"), os.getenv("VIDEO_ID"), os.getenv("SUB_ID")
CHAT_ID, RESO, WM_ID = int(os.getenv("CHAT_ID")), os.getenv("RESOLUTION"), os.getenv("WM_ID")
WM_POS, RENAME = os.getenv("WM_POS"), os.getenv("RENAME")
last_time = 0

async def prog(c, t, app, mid, action):
    global last_time
    now = time.time()
    if now - last_time > 10 or c == t:
        try: await app.edit_message_text(CHAT_ID, mid, f"⚙️ {action}\n⏳ `{(c/t)*100:.1f}%`\n📦 `{c/1048576:.1f}MB / {t/1048576:.1f}MB`")
        except: pass
        last_time = now

async def dl():
    app = Client("w_down", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    await app.start()
    st = await app.send_message(CHAT_ID, "⚙️ Worker: Preparing Download...")
    v = await app.download_media(VIDEO_ID, file_name="video.mp4", progress=prog, progress_args=(app, st.id, "📥 Video..."))
    s, w = None, None
    if TASK_TYPE == "hsub":
        s = await app.download_media(SUB_ID, progress=prog, progress_args=(app, st.id, "📥 Subtitle..."))
        if WM_ID != "none": w = await app.download_media(WM_ID, file_name="wm.png", progress=prog, progress_args=(app, st.id, "📥 Watermark..."))
    await app.edit_message_text(CHAT_ID, st.id, "🔥 **Worker: Processing Started!**")
    await app.stop()
    return v, s, w, st.id

def enc(v, s, w):
    out = RENAME if RENAME != "none" else "out.mp4"
    if TASK_TYPE == "hsub":
        sub = os.path.abspath(s).replace('\\', '/')
        if w: cmd = ["ffmpeg", "-y", "-i", v, "-i", w, "-filter_complex", f"[0:v]subtitles='{sub}':charenc=UTF-8[sub];[1:v]scale=200:-1[wm];[sub][wm]overlay={'20:20' if WM_POS=='TL' else 'W-w-20:20'}", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "34", "-c:a", "aac", out]
        else: cmd = ["ffmpeg", "-y", "-i", v, "-vf", f"subtitles='{sub}':charenc=UTF-8", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "34", "-c:a", "aac", out]
    elif TASK_TYPE == "resize": 
        cmd = ["ffmpeg", "-y", "-i", v, "-vf", f"scale=-2:{RESO}", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "34", "-c:a", "aac", out]
    elif TASK_TYPE == "extract": 
        out = "extracted_sub.srt"
        # Ultra Fast Extract - Stream Copy instead of encode
        cmd = ["ffmpeg", "-y", "-i", v, "-map", "0:s:0", "-c:s", "copy", out] 
    
    p = subprocess.run(cmd, capture_output=True, text=True)
    return out, p.returncode, p.stderr

async def up(out, rc, err, mid):
    app = Client("w_up", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    await app.start()
    if rc == 0 and os.path.exists(out) and os.path.getsize(out) > 0:
        await app.send_document(CHAT_ID, document=out, caption="✅ Completed!", progress=prog, progress_args=(app, mid, "📤 Uploading..."))
        await app.delete_messages(CHAT_ID, mid)
    else: await app.edit_message_text(CHAT_ID, mid, f"❌ **Error:** `{err[-500:]}`")
    await app.stop()

if __name__ == "__main__":
    v, s, w, mid = asyncio.run(dl())
    out, rc, err = enc(v, s, w)
    asyncio.run(up(out, rc, err, mid))
