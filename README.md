# 🤖 All-in-One Media Telegram Bot

Features:
- 🎬 YouTube Details (Title, Channel, Thumbnail)
- ⬇️ YouTube Downloader (MP3 link)
- 📸 Instagram Video/Reel Downloader
- 🎵 TikTok Downloader (No Watermark)
- 🖼️ Remove Background (remove.bg API)
- ✅ All details in monospace (tap to copy!)
- ✅ Main keyboard markup buttons
- ✅ Railway deployment ready

---

## 🚀 Setup Guide

### Step 1 — Get Bot Token
1. Open Telegram → search `@BotFather`
2. Send `/newbot`
3. Give it a name & username
4. Copy the token → `BOT_TOKEN`

### Step 2 — Get RapidAPI Key (for YT/IG/TT download)
1. Go to https://rapidapi.com
2. Sign up (free)
3. Subscribe to these free APIs:
   - `youtube-mp36` → YouTube MP3
   - `instagram-downloader-download-instagram-videos-stories`
   - `tiktok-downloader-download-tiktok-videos-without-watermark`
4. Copy your key → `RAPID_API_KEY`

### Step 3 — Get Remove.bg API Key (optional)
1. Go to https://www.remove.bg/api
2. Sign up (50 free credits/month)
3. Copy API key → `REMOVE_BG_API_KEY`

---

## 🚂 Deploy on Railway

### Method 1 — GitHub (recommended)
1. Push this folder to GitHub
2. Go to https://railway.app
3. New Project → Deploy from GitHub
4. Select your repo
5. Go to **Variables** tab, add:
   ```
   BOT_TOKEN = your_token
   RAPID_API_KEY = your_key
   REMOVE_BG_API_KEY = your_key
   ```
6. Railway auto-deploys! ✅

### Method 2 — Railway CLI
```bash
npm install -g @railway/cli
railway login
railway init
railway up
railway variables set BOT_TOKEN=xxx RAPID_API_KEY=xxx
```

---

## 💻 Run Locally
```bash
pip install -r requirements.txt
export BOT_TOKEN=your_token
export RAPID_API_KEY=your_key
export REMOVE_BG_API_KEY=your_key
python bot.py
```

---

## 📱 Bot Commands
| Command | Description |
|---------|-------------|
| `/start` | Start the bot |
| `/help` | Show help |
| `/ytdetails <url>` | YouTube details |
| `/ytdownload <url>` | YouTube download |
| `/igdownload <url>` | Instagram download |
| `/ttdownload <url>` | TikTok download |
| `/removebg` | Remove background (then send photo) |

---

## 📁 Files
```
telegram-bot/
├── bot.py           ← Main bot code
├── requirements.txt ← Dependencies
├── Procfile         ← Railway process config
├── .env.example     ← Environment variables template
└── README.md        ← This file
```
