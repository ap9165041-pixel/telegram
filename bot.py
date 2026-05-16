import os, re, io, logging, requests
from PIL import Image
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN         = os.environ.get("BOT_TOKEN", "8345172518:AAHahPKnJZwKZ-SIp97vBtNyMyyRXZ-Gw7M")
REMOVE_BG_API_KEY = os.environ.get("REMOVE_BG_API_KEY", "ssgbLxpM5sZT3eAxsJFLzJZ4")

YT_REGEX = re.compile(r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[\w\-]+')
IG_REGEX = re.compile(r'(https?://)?(www\.)?instagram\.com/')
TT_REGEX = re.compile(r'(https?://)?(www\.|vm\.)?tiktok\.com/')

def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎬 YouTube Details"), KeyboardButton("⬇️ YT Downloader")],
        [KeyboardButton("📸 Instagram Downloader"), KeyboardButton("🎵 TikTok Downloader")],
        [KeyboardButton("🖼️ Remove Background"), KeyboardButton("ℹ️ Help")],
    ], resize_keyboard=True)

def mono(t): return f"`{t}`"

def extract_yt_id(url):
    m = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([\w\-]+)', url)
    return m.group(1) if m else None

def bytes_to_img(b): return Image.open(io.BytesIO(b))
def img_to_bytes(img, fmt="PNG"):
    buf = io.BytesIO(); img.save(buf, format=fmt); return buf.getvalue()

def download_video(url, out_dir):
    try:
        import yt_dlp
        ydl_opts = {
            'outtmpl': f'{out_dir}/%(title).60s.%(ext)s',
            'format': 'bestvideo[ext=mp4][filesize<45M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<45M]/best',
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            fpath = ydl.prepare_filename(info)
            if not fpath.endswith('.mp4'):
                fpath = fpath.rsplit('.', 1)[0] + '.mp4'
            return fpath if os.path.exists(fpath) else None
    except Exception as e:
        logger.error(f"yt-dlp error: {e}")
        return None

user_mode = {}

# ─── YouTube Details ───────────────────────────────────────────────────────────
async def handle_yt_details(update: Update, url: str):
    vid = extract_yt_id(url)
    if not vid:
        await update.message.reply_text("❌ Valid YouTube link nahi mili."); return
    msg = await update.message.reply_text("⏳ Fetching details…")
    try:
        r = requests.get(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json", timeout=10)
        d = r.json() if r.status_code == 200 else {}
        title   = d.get("title", "N/A")
        channel = d.get("author_name", "N/A")
        thumb   = d.get("thumbnail_url", f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg")
        video_url = f"https://www.youtube.com/watch?v={vid}"
        caption = (
            f"🎬 *YouTube Video Details*\n\n"
            f"📌 *Title:*\n{mono(title)}\n\n"
            f"👤 *Channel:*\n{mono(channel)}\n\n"
            f"🆔 *Video ID:*\n{mono(vid)}\n\n"
            f"🖼️ *Thumbnail URL:*\n{mono(thumb)}\n\n"
            f"🔗 *Video URL:*\n{mono(video_url)}"
        )
        try:
            await update.message.reply_photo(photo=thumb, caption=caption, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await update.message.reply_text(caption, parse_mode=ParseMode.MARKDOWN)
        await msg.delete()
    except Exception as e:
        logger.error(e); await msg.edit_text(f"❌ Error: `{e}`", parse_mode=ParseMode.MARKDOWN)

# ─── YouTube Download ──────────────────────────────────────────────────────────
async def handle_yt_download(update: Update, url: str):
    vid = extract_yt_id(url)
    if not vid:
        await update.message.reply_text("❌ Valid YouTube link nahi mili."); return
    msg = await update.message.reply_text("⬇️ YouTube video download ho raha hai… thoda wait karo ⏳")
    tmp = "/tmp/ytdl"; os.makedirs(tmp, exist_ok=True)
    try:
        canonical = f"https://www.youtube.com/watch?v={vid}"
        fpath = download_video(canonical, tmp)
        if not fpath:
            await msg.edit_text("❌ Video download nahi hua. Shayad age-restricted ho."); return
        size_mb = os.path.getsize(fpath) / 1_048_576
        if size_mb > 49:
            os.remove(fpath); await msg.edit_text(f"⚠️ Video bahut bada hai ({size_mb:.1f} MB). Chhota video try karo."); return
        await msg.edit_text(f"📤 Upload ho raha hai ({size_mb:.1f} MB)…")
        with open(fpath, "rb") as f:
            await update.message.reply_video(video=f, caption=f"✅ *YouTube Video*\n🔗 {mono(canonical)}", parse_mode=ParseMode.MARKDOWN, supports_streaming=True)
        os.remove(fpath); await msg.delete()
    except Exception as e:
        logger.error(e); await msg.edit_text(f"❌ Error: `{e}`", parse_mode=ParseMode.MARKDOWN)

# ─── Instagram Download ────────────────────────────────────────────────────────
async def handle_ig_download(update: Update, url: str):
    if not IG_REGEX.search(url):
        await update.message.reply_text("❌ Valid Instagram link nahi mili."); return
    msg = await update.message.reply_text("📸 Instagram video download ho raha hai… ⏳")
    tmp = "/tmp/igdl"; os.makedirs(tmp, exist_ok=True)
    try:
        fpath = download_video(url, tmp)
        if not fpath:
            await msg.edit_text("❌ Download nahi hua. Private account ho sakta hai."); return
        size_mb = os.path.getsize(fpath) / 1_048_576
        if size_mb > 49:
            os.remove(fpath); await msg.edit_text(f"⚠️ File bahut badi ({size_mb:.1f} MB)."); return
        await msg.edit_text(f"📤 Upload ho raha hai ({size_mb:.1f} MB)…")
        with open(fpath, "rb") as f:
            await update.message.reply_video(video=f, caption="✅ *Instagram Video*", parse_mode=ParseMode.MARKDOWN, supports_streaming=True)
        os.remove(fpath); await msg.delete()
    except Exception as e:
        logger.error(e); await msg.edit_text(f"❌ Error: `{e}`", parse_mode=ParseMode.MARKDOWN)

# ─── TikTok Download ───────────────────────────────────────────────────────────
async def handle_tt_download(update: Update, url: str):
    if not TT_REGEX.search(url):
        await update.message.reply_text("❌ Valid TikTok link nahi mili."); return
    msg = await update.message.reply_text("🎵 TikTok video download ho raha hai… ⏳")
    tmp = "/tmp/ttdl"; os.makedirs(tmp, exist_ok=True)
    try:
        fpath = download_video(url, tmp)
        if not fpath:
            await msg.edit_text("❌ Download nahi hua."); return
        size_mb = os.path.getsize(fpath) / 1_048_576
        if size_mb > 49:
            os.remove(fpath); await msg.edit_text(f"⚠️ File bahut badi ({size_mb:.1f} MB)."); return
        await msg.edit_text(f"📤 Upload ho raha hai ({size_mb:.1f} MB)…")
        with open(fpath, "rb") as f:
            await update.message.reply_video(video=f, caption="✅ *TikTok Video* (No Watermark)", parse_mode=ParseMode.MARKDOWN, supports_streaming=True)
        os.remove(fpath); await msg.delete()
    except Exception as e:
        logger.error(e); await msg.edit_text(f"❌ Error: `{e}`", parse_mode=ParseMode.MARKDOWN)

# ─── Remove Background ─────────────────────────────────────────────────────────
async def handle_bg_remove(update: Update, photo_bytes: bytes):
    msg = await update.message.reply_text("✂️ remove.bg se background remove ho raha hai… ⏳")
    if not REMOVE_BG_API_KEY:
        await msg.edit_text(
            "❌ *REMOVE_BG_API_KEY set nahi hai!*\n\n"
            f"Railway Variables mein add karo:\n{mono('REMOVE_BG_API_KEY = your_key')}\n\n"
            f"Free key: {mono('https://www.remove.bg/dashboard#api-key')}",
            parse_mode=ParseMode.MARKDOWN); return
    try:
        response = requests.post(
            "https://api.remove.bg/v1.0/removebg",
            files={"image_file": ("image.png", photo_bytes, "image/png")},
            data={"size": "auto"},
            headers={"X-Api-Key": REMOVE_BG_API_KEY},
            timeout=60,
        )
        if response.status_code != 200:
            err = response.json().get("errors", [{}])[0].get("title", response.text[:100])
            await msg.edit_text(f"❌ remove.bg error: `{err}`", parse_mode=ParseMode.MARKDOWN); return

        img_rgba = bytes_to_img(response.content).convert("RGBA")
        credits  = response.headers.get("X-Credits-Remaining", "?")

        buf_t = io.BytesIO(img_to_bytes(img_rgba, "PNG")); buf_t.name = "transparent.png"

        white = Image.new("RGBA", img_rgba.size, (255, 255, 255, 255))
        white.paste(img_rgba, mask=img_rgba.split()[3])
        buf_w = io.BytesIO(img_to_bytes(white.convert("RGB"), "PNG")); buf_w.name = "white_bg.png"

        black = Image.new("RGBA", img_rgba.size, (0, 0, 0, 255))
        black.paste(img_rgba, mask=img_rgba.split()[3])
        buf_b = io.BytesIO(img_to_bytes(black.convert("RGB"), "PNG")); buf_b.name = "black_bg.png"

        await msg.delete()
        await update.message.reply_photo(photo=buf_t, caption=f"✅ *Background Removed!*\n🖼 Transparent PNG\n💳 Credits left: {mono(str(credits))}", parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_photo(photo=buf_w, caption="🤍 White background version")
        await update.message.reply_photo(photo=buf_b, caption="🖤 Black background version (thumbnail ke liye best!)")
    except Exception as e:
        logger.error(e); await msg.edit_text(f"❌ BG remove fail: `{e}`", parse_mode=ParseMode.MARKDOWN)

# ─── Commands ──────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 *Welcome {user.first_name}!*\n\n🤖 *All-in-One Media Bot*\n\n"
        f"🎬 YouTube details\n⬇️ YouTube download (direct file!)\n📸 Instagram download\n🎵 TikTok (no watermark)\n🖼️ BG remove (3 versions!)\n\n"
        f"Link paste karo ya buttons use karo 👇",
        parse_mode=ParseMode.MARKDOWN, reply_markup=main_kb()
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Help*\n\n1️⃣ Button → link paste karo\n2️⃣ Ya seedha link paste karo (auto-detect)\n3️⃣ BG remove → button → photo bhejo\n\n💡 *Monospace text = tap to copy!*\n\n"
        "/start /help /ytdetails /ytdownload /igdownload /ttdownload /removebg",
        parse_mode=ParseMode.MARKDOWN, reply_markup=main_kb()
    )

async def cmd_ytdetails(u, c):
    if c.args: await handle_yt_details(u, " ".join(c.args))
    else: user_mode[u.effective_user.id]="yt_details"; await u.message.reply_text("🎬 YouTube link paste karo:")

async def cmd_ytdownload(u, c):
    if c.args: await handle_yt_download(u, " ".join(c.args))
    else: user_mode[u.effective_user.id]="yt_download"; await u.message.reply_text("⬇️ YouTube link paste karo:")

async def cmd_igdownload(u, c):
    if c.args: await handle_ig_download(u, " ".join(c.args))
    else: user_mode[u.effective_user.id]="ig_download"; await u.message.reply_text("📸 Instagram link paste karo:")

async def cmd_ttdownload(u, c):
    if c.args: await handle_tt_download(u, " ".join(c.args))
    else: user_mode[u.effective_user.id]="tt_download"; await u.message.reply_text("🎵 TikTok link paste karo:")

async def cmd_removebg(u, c):
    user_mode[u.effective_user.id]="remove_bg"
    await u.message.reply_text("🖼️ Photo bhejo — background remove kar deta hoon:")

# ─── Message Router ────────────────────────────────────────────────────────────
async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    photo_bytes = await file.download_as_bytearray()
    await handle_bg_remove(update, bytes(photo_bytes))

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uid = update.effective_user.id
    mode = user_mode.get(uid, "auto")

    btn_map = {
        "🎬 YouTube Details": ("yt_details", "🎬 YouTube link paste karo:"),
        "⬇️ YT Downloader": ("yt_download", "⬇️ YouTube link paste karo (max 49MB):"),
        "📸 Instagram Downloader": ("ig_download", "📸 Instagram post/reel link paste karo:"),
        "🎵 TikTok Downloader": ("tt_download", "🎵 TikTok link paste karo:"),
        "🖼️ Remove Background": ("remove_bg", "🖼️ Ab ek photo bhejo:"),
    }
    if text in btn_map:
        user_mode[uid], prompt = btn_map[text]
        await update.message.reply_text(prompt); return
    if text == "ℹ️ Help":
        await help_cmd(update, context); return

    if YT_REGEX.search(text):
        if mode == "yt_download": await handle_yt_download(update, text)
        else: await handle_yt_details(update, text)
    elif IG_REGEX.search(text):
        await handle_ig_download(update, text)
    elif TT_REGEX.search(text):
        await handle_tt_download(update, text)
    else:
        await update.message.reply_text("❓ YouTube / Instagram / TikTok link paste karo, ya buttons use karo 👇", reply_markup=main_kb())

# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable set nahi hai!")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("ytdetails", cmd_ytdetails))
    app.add_handler(CommandHandler("ytdownload", cmd_ytdownload))
    app.add_handler(CommandHandler("igdownload", cmd_igdownload))
    app.add_handler(CommandHandler("ttdownload", cmd_ttdownload))
    app.add_handler(CommandHandler("removebg", cmd_removebg))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    logger.info("✅ Bot polling shuru…")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
