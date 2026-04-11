import os
import asyncio
import yt_dlp
import aiohttp
import threading
import time
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ========== CONFIG ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))
ADMIN_IDS = [8217006573]  # 👈 YAHAN APNA TELEGRAM USER ID DALO

# ========== WEB SERVER ==========
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "🤖 Bot Running", "service": "Video Downloader"})

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

def run_server():
    app.run(host="0.0.0.0", port=PORT)

def keep_alive():
    """Har 5 min mein khud ko ping karo"""
    while True:
        time.sleep(300)
        try:
            import requests
            requests.get(f"http://localhost:{PORT}/health")
        except:
            pass

# ========== VIDEO DOWNLOAD ==========
async def download_video(url: str):
    """yt-dlp se video download karo"""
    try:
        # Async run ke liye
        loop = asyncio.get_event_loop()
        
        def extract():
            ydl_opts = {
                'format': 'best[filesize<50M]',  # 50MB limit (Telegram)
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Direct URL nikalna
                formats = info.get('formats', [])
                
                # Best format select karo (720p ya 1080p, <50MB)
                best_format = None
                for f in formats:
                    if f.get('filesize') and f['filesize'] < 50*1024*1024:  # 50MB
                        if f.get('height') in [720, 1080]:
                            best_format = f
                            break
                
                # Agar nahi mila toh first best le lo
                if not best_format and formats:
                    best_format = formats[0]
                
                return {
                    "status": "success",
                    "url": best_format.get('url') if best_format else None,
                    "title": info.get('title', 'video'),
                    "platform": info.get('extractor', 'unknown'),
                    "duration": info.get('duration', 0),
                    "thumbnail": info.get('thumbnail', '')
                }
        
        # Run in thread (yt-dlp blocking hai)
        result = await loop.run_in_executor(None, extract)
        return result
        
    except Exception as e:
        return {"status": "error", "text": str(e)}

# ========== COMMANDS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"🎬 *Hey {user.first_name}!*\n\n"
        f"Mujhe video link bhejo:\n"
        f"• YouTube • TikTok • Instagram\n"
        f"• Twitter • Facebook • Reddit\n"
        f"• SoundCloud • Vimeo • 1000+ sites\n\n"
        f"⚡ *No watermark • HD Quality*",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if not url.startswith("http"):
        return
    
    # Processing
    msg = await update.message.reply_text("⏳ Processing... Please wait!")
    
    # Download
    result = await download_video(url)
    
    if result.get("status") == "success" and result.get("url"):
        download_url = result["url"]
        title = result.get("title", "video")
        
        keyboard = [[InlineKeyboardButton("📥 Download Now", url=download_url)]]
        
        await msg.edit_text(
            f"✅ *{title[:50]}...*\n\n"
            f"👇 Click to download:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        error = result.get("text", "Download failed")
        await msg.edit_text(f"❌ Failed: {error}")

# ========== MAIN ==========
def main():
    # Web server start
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    print("🌐 Server started on port", PORT)
    
    # Bot setup
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
