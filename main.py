# main.py
import os
import json
import threading
import sys
import asyncio
import logging
from datetime import datetime

import discord
from discord.ext import commands
from dotenv import load_dotenv
from openai import OpenAI

# --- Env & logging ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

API_KEY = os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "shape-medium")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Optional: local ffmpeg.exe alongside this file (Windows convenience)
FFMPEG_PATH = os.path.join(os.path.dirname(__file__), "ffmpeg.exe")
if os.path.isfile(FFMPEG_PATH):
    os.environ["PATH"] = os.path.dirname(FFMPEG_PATH) + os.pathsep + os.environ.get("PATH", "")

# --- Shape.inc client (OpenAI-compatible base_url) ---
_raw_shapes = OpenAI(api_key=API_KEY, base_url="https://api.shapes.inc/v1/")

class ShapesAdapter:
    """Adapts the OpenAI-style client to a simple .chat(model, message) interface expected by the cog."""
    def __init__(self, client):
        self.client = client

    def chat(self, model_name: str, message: str) -> str:
        try:
            resp = self.client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": message}],
            )
            # Handle both old/new shapes of responses
            if hasattr(resp, "choices") and resp.choices:
                msg = resp.choices[0].message
                # OpenAI SDK returns .content; if dict-like, coerce to str
                return msg.content if isinstance(msg.content, str) else str(msg.content)
            return "(no response)"
        except Exception as e:
            return f"Shape error: {e!r}"

shapes_client = ShapesAdapter(_raw_shapes)

# --- Discord intents ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True  # needed for VC join/move/play
intents.guilds = True

# --- Dynamic prefix (reads config.json if present) ---
def get_prefix(bot, message):
    if not hasattr(bot, "prefixes"):
        try:
            with open(os.path.join(os.path.dirname(__file__), "config.json"), "r", encoding="utf-8") as f:
                bot.prefixes = json.load(f)
        except Exception:
            bot.prefixes = {}
    if message.guild:
        return bot.prefixes.get(str(message.guild.id), "!s_")
    return "!s_"

bot = commands.Bot(command_prefix=get_prefix, intents=intents)
bot.remove_command("help")

# Make Shape available to cogs
bot.shapes_client = shapes_client
bot.shape_model_name = MODEL_NAME

@bot.event
async def on_ready():
    logging.info("[BOT] Logged in as %s (%s)", bot.user, bot.user.id)
    # Set bot status to Streaming with description and link (attachment link)
    activity = discord.Streaming(
        name="Talking to People in Souls",
        url="https://www.twitch.tv/souls_server"
    )
    await bot.change_presence(activity=activity, status=discord.Status.online)
    try:
        synced = await bot.tree.sync()
        logging.info("[INFO] Synced %d slash commands.", len(synced))
    except Exception as e:
        logging.error("[ERROR] Failed to sync slash commands: %s", e)

async def load_cogs():
    import chat_commands
    import talk_commands
    try:
        await chat_commands.setup(bot)
        logging.info("[BOT] Loaded chat_commands")
    except Exception as e:
        logging.exception("[ERROR] Failed to load chat_commands: %s", e)
    try:
        await talk_commands.setup(bot)
        logging.info("[BOT] Loaded talk_commands")
    except Exception as e:
        logging.exception("[ERROR] Failed to load talk_commands: %s", e)

def run_flask():
    try:
        from tara_flask_server import app as flask_app
        port = int(os.getenv("PORT", "5000"))   # <-- Render will inject PORT
        flask_app.run(host="0.0.0.0", port=port, debug=False)
    except Exception as e:
        logging.warning("Flask server not started: %s", e)

def test_shapes_connectivity():
    try:
        resp = _raw_shapes.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": "ping"}],
        )
        logging.info("[BOT] CONNECTED TO SHAPE.INC {Model: %s}", MODEL_NAME)
    except Exception as e:
        logging.error("[BOT] ERROR: Could not connect to SHAPE.INC with model '%s': %s", MODEL_NAME, e)

async def main():
    if not DISCORD_TOKEN:
        raise RuntimeError("Set DISCORD_TOKEN in environment.")
    # Start Flask (optional)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logging.info("🌐 Tara Web Dashboard thread started at http://localhost:5000")

    test_shapes_connectivity()

    await load_cogs()
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
