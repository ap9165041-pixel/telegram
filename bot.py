"""
╔══════════════════════════════════════════════════════════════╗
║           🤖  ALL-IN-ONE MEDIA + AI BOT  (Telegram)          ║
║                                                              ║
║  📺 YouTube Details     ⬇️  YouTube Download                 ║
║  📸 Instagram DL        🎵  TikTok Download                  ║
║  ✂️  BG Remover (AI)    ✨  Image Enhancer (AI)              ║
║  🔄  Object Changer (AI)   ✍️  AI Text Rewriter              ║
╚══════════════════════════════════════════════════════════════╝

INSTALL:
  pip install python-telegram-bot yt-dlp requests pillow replicate anthropic

API KEYS NEEDED:
  1. BOT_TOKEN           → Telegram @BotFather
  2. REMOVE_BG_API_KEY   → https://www.remove.bg/dashboard#api-key
  3. REPLICATE_API_TOKEN → https://replicate.com/account/api-tokens
  4. ANTHROPIC_API_KEY  → https://console.anthropic.com/settings/api-keys

RUN:
  python youtube_telegram_bot.py
"""

import os
import io
import re
import base64
import logging
import requests
import yt_dlp
import replicate
import anthropic

from PIL import Image

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

# ══════════════════════════════════════════════════════════════
#  🔑  TOKENS — FILL THESE IN
# ══════════════════════════════════════════════════════════════
BOT_TOKEN            = "8345172518:AAHahPKnJZwKZ-SIp97vBtNyMyyRXZ-Gw7M"
REMOVE_BG_API_KEY    = "ssgbLxpM5sZT3eAxsJFLzJZ4"      # https://www.remove.bg/dashboard#api-key
REPLICATE_API_TOKEN  = "fghfghfgh"   # https://replicate.com/account/api-tokens
ANTHROPIC_API_KEY    = "gfhhg"      # https://console.anthropic.com/settings/api-keys
# ══════════════════════════════════════════════════════════════

os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Mode constants ─────────────────────────────────────────────────────────
MODE_YT_DETAILS   = "🔍 YouTube Details"
MODE_YT_DOWNLOAD  = "⬇️ YouTube Download"
MODE_IG_DOWNLOAD  = "📸 Instagram Download"
MODE_TT_DOWNLOAD  = "🎵 TikTok Download"
MODE_BG_REMOVE    = "✂️ BG Remover"

ALL_MODES = (
    MODE_YT_DETAILS, MODE_YT_DOWNLOAD,
    MODE_IG_DOWNLOAD, MODE_TT_DOWNLOAD,
    MODE_BG_REMOVE,
)

# Per-user state
user_modes:   dict[int, str] = {}   # current mode
user_pending: dict[int, dict] = {}  # pending data (e.g. image waiting for prompt)

# ── Keyboard  (3 rows × 2-3 buttons) ──────────────────────────────────────
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(MODE_YT_DETAILS),  KeyboardButton(MODE_YT_DOWNLOAD)],
        [KeyboardButton(MODE_IG_DOWNLOAD), KeyboardButton(MODE_TT_DOWNLOAD)],
        [KeyboardButton(MODE_BG_REMOVE)],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)

# ── Regex ──────────────────────────────────────────────────────────────────
YT_REGEX = re.compile(
    r"(https?://)?(www\.)?"
    r"(youtube\.com/(watch\?v=|shorts/|embed/)|youtu\.be/)"
    r"([A-Za-z0-9_\-]{11})"
)
IG_REGEX = re.compile(r"https?://(www\.)?instagram\.com/")
TT_REGEX = re.compile(r"https?://(www\.|vm\.)?tiktok\.com/")


# ══════════════════════════════════════════════════════════════════════════
#  HELPERS — YouTube / General
# ══════════════════════════════════════════════════════════════════════════

def extract_yt_id(text: str):
    m = YT_REGEX.search(text)
    return m.group(5) if m else None

def get_best_thumbnail(vid: str) -> str:
    for q in ["maxresdefault", "sddefault", "hqdefault", "default"]:
        url = f"https://img.youtube.com/vi/{vid}/{q}.jpg"
        try:
            r = requests.head(url, timeout=5)
            if r.status_code == 200 and int(r.headers.get("content-length", 0)) > 1000:
                return url
        except Exception:
            pass
    return f"https://img.youtube.com/vi/{vid}/default.jpg"

def truncate(text: str, limit: int = 700) -> str:
    if not text:
        return "_No description._"
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"

def fmt_views(n: int) -> str:
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.1f}K"
    return str(n)

def fmt_dur(secs: int) -> str:
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s" if h else f"{m}m {s}s"

def fetch_info(url: str) -> dict:
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
        return ydl.extract_info(url, download=False)

def download_video(url: str, out_path: str, max_mb: int = 45) -> str | None:
    outtmpl = os.path.join(out_path, "%(id)s.%(ext)s")
    ydl_opts = {
        "quiet": True, "no_warnings": True, "outtmpl": outtmpl,
        "format": f"bestvideo[ext=mp4][filesize<{max_mb}M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<{max_mb}M]/best",
        "merge_output_format": "mp4",
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info  = ydl.extract_info(url, download=True)
        fname = ydl.prepare_filename(info)
        if not os.path.exists(fname):
            fname = fname.rsplit(".", 1)[0] + ".mp4"
        return fname if os.path.exists(fname) else None

def img_to_bytes(img: Image.Image, fmt="PNG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()

def bytes_to_img(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))

async def get_photo_bytes(update: Update) -> bytes | None:
    """Download the photo from a Telegram message."""
    if not update.message.photo:
        return None
    photo = update.message.photo[-1]   # highest resolution
    file  = await photo.get_file()
    buf   = io.BytesIO()
    await file.download_to_memory(buf)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════
#  AI HELPER — Replicate (image-in → image-out)
# ══════════════════════════════════════════════════════════════════════════

def replicate_enhance(image_bytes: bytes) -> bytes:
    """
    AI Image Enhancer — uses Clarity Upscaler on Replicate.
    Model: philz1337x/clarity-upscaler
    Free tier: ~10 free predictions/month
    """
    b64 = base64.b64encode(image_bytes).decode()
    data_uri = f"data:image/png;base64,{b64}"

    output = replicate.run(
        "philz1337x/clarity-upscaler:dfad41707589d68ecdccd1dfa600d55a208f9310748e44bfe35b4a6291453d5e",
        input={
            "image": data_uri,
            "scale_factor": 2,
            "dynamic": 6,
            "creativity": 0.35,
            "resemblance": 0.6,
            "tiling_width": 112,
            "tiling_height": 144,
            "output_format": "png",
        },
    )
    # output is a URL or file-like object
    if isinstance(output, str):
        return requests.get(output, timeout=60).content
    if isinstance(output, list):
        url = output[0]
        if isinstance(url, str):
            return requests.get(url, timeout=60).content
        return url.read()
    return output.read()


def replicate_object_replace(image_bytes: bytes, prompt: str) -> bytes:
    """
    AI Object Changer — uses Stable Diffusion Inpainting via Replicate.
    Model: stability-ai/stable-diffusion-inpainting
    The user provides a text prompt like 'replace car with bike'.
    We use img2img with the prompt to transform the image.
    """
    b64 = base64.b64encode(image_bytes).decode()
    data_uri = f"data:image/png;base64,{b64}"

    output = replicate.run(
        "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
        input={
            "image": data_uri,
            "prompt": prompt,
            "prompt_strength": 0.75,
            "num_inference_steps": 30,
            "guidance_scale": 7.5,
        },
    )
    if isinstance(output, list):
        url = output[0]
        if isinstance(url, str):
            return requests.get(url, timeout=60).content
        return url.read()
    if isinstance(output, str):
        return requests.get(output, timeout=60).content
    return output.read()


# ══════════════════════════════════════════════════════════════════════════
#  MODE HANDLERS — YouTube / Social
# ══════════════════════════════════════════════════════════════════════════

async def handle_yt_details(update: Update, url: str):
    vid = extract_yt_id(url)
    if not vid:
        await update.message.reply_text("❌ Valid YouTube link nahi mili. Dobara try karo.")
        return

    msg = await update.message.reply_text("⏳ YouTube details fetch ho rahi hain…")
    try:
        canonical = f"https://www.youtube.com/watch?v={vid}"
        info = fetch_info(canonical)

        title    = info.get("title", "Unknown")
        desc     = truncate(info.get("description", ""))
        uploader = info.get("uploader", "Unknown")
        views    = fmt_views(info.get("view_count", 0))
        dur      = fmt_dur(info.get("duration", 0))
        raw_d    = info.get("upload_date", "")
        date     = f"{raw_d[:4]}-{raw_d[4:6]}-{raw_d[6:]}" if len(raw_d) == 8 else "?"
        likes    = fmt_views(info.get("like_count", 0)) if info.get("like_count") else "N/A"
        thumb    = get_best_thumbnail(vid)

        caption = (
            f"🎬 *{title}*\n"
            f"👤 {uploader}  ·  📅 {date}  ·  ⏱ {dur}  ·  👁 {views}  ·  👍 {likes}"
        )

        await msg.delete()

        await update.message.reply_photo(photo=thumb, caption=caption, parse_mode="Markdown")

        await update.message.reply_text(
            f"📋 *Copyable Details* — tap karke copy karo:\n\n"
            f"🎬 *Title:*\n`{title}`\n\n"
            f"👤 *Channel:*\n`{uploader}`\n\n"
            f"📅 *Date:*\n`{date}`\n\n"
            f"⏱ *Duration:*\n`{dur}`\n\n"
            f"👁 *Views:*\n`{views}`\n\n"
            f"👍 *Likes:*\n`{likes}`\n\n"
            f"🔗 *URL:*\n`{canonical}`",
            parse_mode="Markdown",
        )

        await update.message.reply_text(
            f"📝 *Description:*\n\n`{desc}`",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(e)
        await msg.edit_text(f"❌ Error: `{e}`", parse_mode="Markdown")


async def handle_yt_download(update: Update, url: str):
    vid = extract_yt_id(url)
    if not vid:
        await update.message.reply_text("❌ Valid YouTube link nahi mili.")
        return
    msg = await update.message.reply_text("⬇️ YouTube video download ho raha hai… thoda wait karo ⏳")
    tmp = "/tmp/ytdl"; os.makedirs(tmp, exist_ok=True)
    try:
        canonical = f"https://www.youtube.com/watch?v={vid}"
        fpath = download_video(canonical, tmp)
        if not fpath:
            await msg.edit_text("❌ Video download nahi hua.")
            return
        size_mb = os.path.getsize(fpath) / 1_048_576
        if size_mb > 49:
            os.remove(fpath)
            await msg.edit_text(f"⚠️ Video bahut bada hai ({size_mb:.1f} MB). Chhota video try karo.")
            return
        await msg.edit_text(f"📤 Upload ho raha hai ({size_mb:.1f} MB)…")
        with open(fpath, "rb") as f:
            await update.message.reply_video(video=f, caption=f"✅ YouTube Video\n🔗 {canonical}", supports_streaming=True)
        os.remove(fpath); await msg.delete()
    except Exception as e:
        logger.error(e)
        await msg.edit_text(f"❌ Error: `{e}`", parse_mode="Markdown")


async def handle_ig_download(update: Update, url: str):
    if not IG_REGEX.search(url):
        await update.message.reply_text("❌ Valid Instagram link nahi mili.")
        return
    msg = await update.message.reply_text("📸 Instagram video download ho raha hai… ⏳")
    tmp = "/tmp/igdl"; os.makedirs(tmp, exist_ok=True)
    try:
        fpath = download_video(url, tmp)
        if not fpath:
            await msg.edit_text("❌ Download nahi hua. Private account ho sakta hai.")
            return
        size_mb = os.path.getsize(fpath) / 1_048_576
        if size_mb > 49:
            os.remove(fpath); await msg.edit_text(f"⚠️ File bahut badi ({size_mb:.1f} MB)."); return
        await msg.edit_text(f"📤 Upload ho raha hai ({size_mb:.1f} MB)…")
        with open(fpath, "rb") as f:
            await update.message.reply_video(video=f, caption="✅ Instagram Video", supports_streaming=True)
        os.remove(fpath); await msg.delete()
    except Exception as e:
        logger.error(e)
        await msg.edit_text(f"❌ Error: `{e}`", parse_mode="Markdown")


async def handle_tt_download(update: Update, url: str):
    if not TT_REGEX.search(url):
        await update.message.reply_text("❌ Valid TikTok link nahi mili.")
        return
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
            await update.message.reply_video(video=f, caption="✅ TikTok Video", supports_streaming=True)
        os.remove(fpath); await msg.delete()
    except Exception as e:
        logger.error(e)
        await msg.edit_text(f"❌ Error: `{e}`", parse_mode="Markdown")


# ══════════════════════════════════════════════════════════════════════════
#  MODE HANDLERS — AI Image Tools
# ══════════════════════════════════════════════════════════════════════════

async def handle_bg_remove(update: Update, photo_bytes: bytes):
    """
    ✂️ BG Remover — uses remove.bg API (professional quality)
    https://www.remove.bg/dashboard#api-key
    Free tier: 50 API calls/month
    """
    msg = await update.message.reply_text("✂️ remove.bg se background remove ho raha hai… ⏳")
    try:
        # Call remove.bg API
        response = requests.post(
            "https://api.remove.bg/v1.0/removebg",
            files={"image_file": ("image.png", photo_bytes, "image/png")},
            data={"size": "auto"},
            headers={"X-Api-Key": REMOVE_BG_API_KEY},
            timeout=60,
        )

        if response.status_code != 200:
            err = response.json().get("errors", [{}])[0].get("title", response.text)
            await msg.edit_text(
                f"❌ remove.bg API error: `{err}`\n\n"
                "💡 Check karo REMOVE_BG_API_KEY sahi hai ya nahi.\n"
                "🔗 https://www.remove.bg/dashboard#api-key",
                parse_mode="Markdown",
            )
            return

        # response.content = PNG with transparent background
        result_bytes = response.content
        img_rgba = bytes_to_img(result_bytes).convert("RGBA")

        # 1️⃣ Transparent PNG
        buf_transparent = io.BytesIO(img_to_bytes(img_rgba, "PNG"))
        buf_transparent.name = "bg_removed_transparent.png"

        # 2️⃣ White background version
        white_bg = Image.new("RGBA", img_rgba.size, (255, 255, 255, 255))
        white_bg.paste(img_rgba, mask=img_rgba.split()[3])
        buf_white = io.BytesIO(img_to_bytes(white_bg.convert("RGB"), "PNG"))
        buf_white.name = "bg_removed_white.png"

        # 3️⃣ Black background version (looks great for thumbnails)
        black_bg = Image.new("RGBA", img_rgba.size, (0, 0, 0, 255))
        black_bg.paste(img_rgba, mask=img_rgba.split()[3])
        buf_black = io.BytesIO(img_to_bytes(black_bg.convert("RGB"), "PNG"))
        buf_black.name = "bg_removed_black.png"

        # Credits remaining
        credits = response.headers.get("X-Credits-Remaining", "?")

        await msg.delete()

        await update.message.reply_photo(
            photo=buf_transparent,
            caption=(
                "✅ *Background Removed by remove.bg!*\n\n"
                "🖼 Transparent PNG — kisi bhi bg pe use karo\n"
                f"💳 Credits remaining: `{credits}`"
            ),
            parse_mode="Markdown",
        )
        await update.message.reply_photo(
            photo=buf_white,
            caption="🤍 White background version",
        )
        await update.message.reply_photo(
            photo=buf_black,
            caption="🖤 Black background version (thumbnail ke liye best!)",
        )

    except Exception as e:
        logger.error(e)
        await msg.edit_text(f"❌ BG remove fail: `{e}`", parse_mode="Markdown")


async def handle_ai_enhance(update: Update, photo_bytes: bytes):
    """
    ✨ AI Image Enhancer — uses Replicate Clarity Upscaler
    Upscales 2x + improves sharpness, detail, and quality.
    """
    msg = await update.message.reply_text(
        "✨ AI se image enhance ho rahi hai…\n"
        "_(Thoda time lagega — 30-60 seconds)_ ⏳",
        parse_mode="Markdown",
    )
    try:
        enhanced_bytes = replicate_enhance(photo_bytes)

        buf = io.BytesIO(enhanced_bytes)
        buf.name = "enhanced.png"

        await msg.delete()
        await update.message.reply_photo(
            photo=buf,
            caption=(
                "✅ *AI Enhanced Image!*\n\n"
                "🔍 2x Upscaled\n"
                "✨ Sharpness & detail improved\n"
                "🎨 Colors enhanced"
            ),
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(e)
        await msg.edit_text(
            f"❌ Enhance fail hua: `{e}`\n\n"
            "💡 Check karo REPLICATE_API_TOKEN sahi hai ya nahi.",
            parse_mode="Markdown",
        )


async def handle_ai_replace_photo(update: Update, uid: int, photo_bytes: bytes):
    """Step 1 — store photo and ask for prompt."""
    user_pending[uid] = {"mode": "ai_replace", "photo": photo_bytes}
    await update.message.reply_text(
        "🔄 *Object Changer*\n\n"
        "Ab batao kya replace karna hai:\n\n"
        "Example:\n"
        "`replace car with motorcycle`\n"
        "`change blue sky to sunset`\n"
        "`replace shirt with jacket`\n\n"
        "Apna prompt type karo 👇",
        parse_mode="Markdown",
    )


async def handle_ai_replace_prompt(update: Update, uid: int, prompt: str):
    """Step 2 — run object replacement with stored photo + prompt."""
    photo_bytes = user_pending[uid]["photo"]
    user_pending.pop(uid, None)

    msg = await update.message.reply_text(
        f"🔄 AI image process ho rahi hai...\n"
        f"Prompt: _{prompt}_\n\n"
        f"_(30-90 seconds lagenge)_ ⏳",
        parse_mode="Markdown",
    )
    try:
        result_bytes = replicate_object_replace(photo_bytes, prompt)

        buf = io.BytesIO(result_bytes)
        buf.name = "ai_replaced.png"

        await msg.delete()
        await update.message.reply_photo(
            photo=buf,
            caption=(
                f"✅ *Object Changed!*\n\n"
                f"📝 Prompt: `{prompt}`"
            ),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(e)
        await msg.edit_text(
            f"❌ Object change fail: `{e}`\n\n"
            "💡 Check karo REPLICATE_API_TOKEN.",
            parse_mode="Markdown",
        )


# ══════════════════════════════════════════════════════════════════════════
#  MAIN TELEGRAM HANDLERS
# ══════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════
#  MODE HANDLER — AI Text Rewriter (Copyright-Free)
# ══════════════════════════════════════════════════════════════════════════

def ai_rewrite_text(original: str, content_type: str) -> dict:
    """
    Uses Claude API to rewrite title/description to be copyright-free.
    Returns dict with: rewritten, tags, hook
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    system_prompt = (
        "You are an expert YouTube content strategist and SEO copywriter. "
        "Your job is to rewrite titles and descriptions to be completely original, "
        "copyright-free, and more engaging — while keeping the same topic and meaning. "
        "Always respond in JSON format only, no extra text."
    )

    if content_type == "title":
        user_prompt = f"""Rewrite this YouTube title to be copyright-free and more engaging.
Keep same topic, same language (Hindi/English/Hinglish — match original).

Original title: {original}

Respond ONLY in this JSON format:
{{
  "rewritten": "New catchy copyright-free title here",
  "alternative1": "Another version 1",
  "alternative2": "Another version 2",
  "hook": "One-line hook for thumbnail text"
}}"""
    else:
        user_prompt = f"""Rewrite this YouTube description to be copyright-free and SEO-optimized.
Keep same topic and language. Make it engaging and original.

Original description:
{original[:1500]}

Respond ONLY in this JSON format:
{{
  "rewritten": "Full rewritten description here",
  "short_version": "Short 2-3 line version",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    import json
    return json.loads(raw)


async def handle_ai_rewrite(update: Update, text: str):
    """
    ✍️ AI Rewriter — rewrites title or description using Claude AI.
    Auto-detects if input is a title (short) or description (long).
    """
    msg = await update.message.reply_text(
        "✍️ Claude AI se rewrite ho raha hai… ⏳",
    )
    try:
        # Auto-detect: title = short (< 120 chars), description = long
        is_title = len(text) < 120
        content_type = "title" if is_title else "description"
        label = "Title" if is_title else "Description"

        result = ai_rewrite_text(text, content_type)

        import json

        await msg.delete()

        if content_type == "title":
            response_text = (
                f"✍️ *AI Rewriter — {label}*\n\n"
                f"📌 *Original:*\n`{text}`\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ *Rewritten (Copyright-Free):*\n"
                f"`{result.get('rewritten', '')}`\n\n"
                f"🔁 *Alternative 1:*\n"
                f"`{result.get('alternative1', '')}`\n\n"
                f"🔁 *Alternative 2:*\n"
                f"`{result.get('alternative2', '')}`\n\n"
                f"🎯 *Thumbnail Hook:*\n"
                f"`{result.get('hook', '')}`"
            )
        else:
            tags = result.get("tags", [])
            tags_str = "  ".join([f"`#{t}`" for t in tags])
            response_text = (
                f"✍️ *AI Rewriter — {label}*\n\n"
                f"📌 *Original (first 100 chars):*\n`{text[:100]}…`\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ *Rewritten Description:*\n"
                f"`{result.get('rewritten', '')}`\n\n"
                f"📋 *Short Version:*\n"
                f"`{result.get('short_version', '')}`\n\n"
                f"🏷 *Suggested Tags:*\n{tags_str}"
            )

        await update.message.reply_text(response_text, parse_mode="Markdown")

    except Exception as e:
        logger.error(e)
        await msg.edit_text(
            f"❌ AI Rewrite fail: `{e}`\n\n"
            "💡 Check karo ANTHROPIC_API_KEY sahi hai ya nahi.",
            parse_mode="Markdown",
        )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.first_name or "User"
    user_modes[uid] = MODE_YT_DETAILS
    await update.message.reply_text(
        f"👋 *Namaste {name}!*\n\n"
        "🤖 *All-in-One Media + AI Bot* mein aapka swagat hai!\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📺 *YouTube & Social*\n"
        f"  {MODE_YT_DETAILS} — Details fetch karo\n"
        f"  {MODE_YT_DOWNLOAD} — Video download karo\n"
        f"  {MODE_IG_DOWNLOAD} — Instagram reel/post\n"
        f"  {MODE_TT_DOWNLOAD} — TikTok video\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎨 *AI Image Tool*\n"
        f"  {MODE_BG_REMOVE} — Background hatao\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Button dabao → phir link ya photo bhejo! 🚀",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid    = update.effective_user.id
    text   = (update.message.text or "").strip()
    photo  = update.message.photo

    # ── Button press ────────────────────────────────────────────────────
    if text in ALL_MODES:
        user_modes[uid] = text
        user_pending.pop(uid, None)   # clear any pending state

        prompts = {
            MODE_YT_DETAILS:  "🔍 *YouTube Details* mode!\nYouTube link paste karo.",
            MODE_YT_DOWNLOAD: "⬇️ *YouTube Download* mode!\nYouTube link paste karo.",
            MODE_IG_DOWNLOAD: "📸 *Instagram Download* mode!\nInstagram link paste karo.",
            MODE_TT_DOWNLOAD: "🎵 *TikTok Download* mode!\nTikTok link paste karo.",
            MODE_BG_REMOVE:   "✂️ *BG Remover* mode!\nKoi bhi photo bhejo — background remove ho jaayega.",
        }
        await update.message.reply_text(
            prompts[text], parse_mode="Markdown", reply_markup=MAIN_KEYBOARD
        )
        return

    mode = user_modes.get(uid, MODE_YT_DETAILS)

    # ── Photo received ──────────────────────────────────────────────────
    if photo:
        if mode != MODE_BG_REMOVE:
            await update.message.reply_text(
                f"📷 Photo ke liye {MODE_BG_REMOVE} mode select karo!",
                reply_markup=MAIN_KEYBOARD,
            )
            return

        photo_bytes = await get_photo_bytes(update)
        if not photo_bytes:
            await update.message.reply_text("❌ Photo read nahi hua.")
            return

        await handle_bg_remove(update, photo_bytes)
        return

    # ── Text / URL received ─────────────────────────────────────────────
    if not text:
        return

    if mode == MODE_YT_DETAILS:
        await handle_yt_details(update, text)
    elif mode == MODE_YT_DOWNLOAD:
        await handle_yt_download(update, text)
    elif mode == MODE_IG_DOWNLOAD:
        await handle_ig_download(update, text)
    elif mode == MODE_TT_DOWNLOAD:
        await handle_tt_download(update, text)
    elif mode == MODE_BG_REMOVE:
        await update.message.reply_text(
            "📷 Yeh mode photo ke liye hai!\nApni image bhejo.",
            reply_markup=MAIN_KEYBOARD,
        )
    else:
        await update.message.reply_text("Mode choose karo! 👇", reply_markup=MAIN_KEYBOARD)


# ══════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    errors = []
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        errors.append("BOT_TOKEN  (Telegram @BotFather)")
    if REMOVE_BG_API_KEY == "YOUR_REMOVEBG_KEY_HERE":
        errors.append("REMOVE_BG_API_KEY  (https://www.remove.bg/dashboard#api-key)")
    if REPLICATE_API_TOKEN == "YOUR_REPLICATE_TOKEN_HERE":
        errors.append("REPLICATE_API_TOKEN  (https://replicate.com/account/api-tokens)")
    if ANTHROPIC_API_KEY == "YOUR_ANTHROPIC_KEY_HERE":
        errors.append("ANTHROPIC_API_KEY  (https://console.anthropic.com/settings/api-keys)")
    if errors:
        print("\n⚠️  Ye tokens set karo pehle:\n  " + "\n  ".join(errors) + "\n")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO) & ~filters.COMMAND,
        handle_message,
    ))

    logger.info("🤖 Bot chal raha hai… Ctrl+C se band karo.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
