from typing import Optional
import os
import json
import asyncio
import tempfile
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from discord import app_commands, FFmpegPCMAudio

try:
    from gtts import gTTS  # fallback if ElevenLabs not configured
except Exception:  # pragma: no cover
    gTTS = None


# ===== Utilities =====
def _data_path(name: str) -> str:
    return os.path.join(os.path.dirname(__file__), name)


def _now() -> datetime:
    return datetime.utcnow()


async def _generate_tts_audio(text: str) -> str:
    """
    Returns a path to an audio file (wav or mp3) that contains the spoken text.
    Prefers ElevenLabs if ELEVEN_API_KEY is set; otherwise falls back to gTTS if available.
    """
    eleven_api = os.getenv("ELEVEN_API_KEY")
    eleven_voice = os.getenv("ELEVEN_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel (default)
    if eleven_api:
        import requests  # local import to avoid hard dep if unused
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{eleven_voice}"
        headers = {
            "xi-api-key": eleven_api,
            "accept": "audio/mpeg",
            "content-type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": os.getenv("ELEVEN_MODEL_ID", "eleven_multilingual_v2"),
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        fd, path = tempfile.mkstemp(suffix=".mp3")
        with os.fdopen(fd, "wb") as f:
            f.write(resp.content)
        return path

    # gTTS fallback
    if gTTS is None:
        raise RuntimeError("No TTS available: set ELEVEN_API_KEY or install gTTS.")
    tts = gTTS(text=text, lang="en")
    fd, path = tempfile.mkstemp(suffix=".mp3")
    with os.fdopen(fd, "wb") as f:
        tts.write_to_fp(f)
    return path


# ===== TalkCommands Cog =====
class TalkCommands(commands.Cog):
    """
    Voice-channel TTS with simple locking so only one user controls the bot at a time.
    Lock auto-expires after 10 minutes of inactivity.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.lock_file = _data_path("talk_lock.json")
        print("[BOT] Talk_Commands Ready!", flush=True)

    # ---------- Lock helpers ----------
    def _read_lock(self) -> dict:
        try:
            with open(self.lock_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_lock(self, data: dict) -> None:
        with open(self.lock_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _clear_if_expired(self, lock: dict) -> dict:
        ts = lock.get("timestamp")
        if not ts:
            return lock
        try:
            elapsed = (_now() - datetime.fromisoformat(ts)).total_seconds()
            if elapsed > 600:  # 10 minutes
                return {}
        except Exception:
            return {}
        return lock

    # ---------- Prefix command ----------
    @commands.command(name="s_talk", aliases=["talk"])
    async def talk_command(self, ctx: commands.Context, *, message: Optional[str] = None):
        """Join the caller's VC (if any) and speak the Shape API response via TTS."""
        if not message:
            await ctx.send("Usage: `s_talk <message>` (be in a voice channel).")
            return

        # Usage tracking
        usage_path = os.path.join(os.path.dirname(__file__), "vc_usage.json")
        user_id = str(ctx.author.id)
        today = _now().strftime("%Y-%m-%d")
        try:
            with open(usage_path, "r", encoding="utf-8") as f:
                usage = json.load(f)
        except Exception:
            usage = {}
        user_usage = usage.get(user_id, {"date": today, "count": 0})
        if user_usage["date"] != today:
            user_usage = {"date": today, "count": 0}
        if user_usage["count"] >= 5:
            await ctx.send("Your daily Talk with Bot is Over. See ya next day!")
            if ctx.voice_client and ctx.voice_client.is_connected():
                await ctx.voice_client.disconnect()
            try:
                os.remove(self.lock_file)
            except Exception:
                pass
            await ctx.send(f"{ctx.author.display_name} reached daily limit. Lock released. Next person can use the bot.")
            return
        user_usage["count"] += 1
        usage[user_id] = user_usage
        with open(usage_path, "w", encoding="utf-8") as f:
            json.dump(usage, f, indent=2)

        # Check voice channel
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("You need to be **in a voice channel** first.")
            return
        channel: discord.VoiceChannel = ctx.author.voice.channel

        # Locking
        lock = self._read_lock()
        lock = self._clear_if_expired(lock)
        locked_user = lock.get("user_id")

        if locked_user and int(locked_user) != ctx.author.id:
            # Someone else holds the lock
            member = ctx.guild.get_member(int(locked_user))
            holder = member.display_name if member else f"<@{locked_user}>"
            await ctx.send(f"{holder} is currently using voice. Try again later.")
            return

        # At this point caller owns (or acquires) the lock
        lock = {"user_id": str(ctx.author.id), "timestamp": _now().isoformat()}
        self._write_lock(lock)

        # Connect/move
        if ctx.voice_client:
            if ctx.voice_client.channel != channel:
                await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()

        # Get response from Shape API
        try:
            shape_client = getattr(self.bot, "shapes_client", None)
            model_name = getattr(self.bot, "shape_model_name", "shape-medium")
            if not shape_client:
                raise RuntimeError("Shape API client not available.")
            response_text = shape_client.chat(model_name, message)
        except Exception as e:
            await ctx.send(f"Shape API error: `{e}`")
            return

        # Generate audio and play
        try:
            audio_path = await _generate_tts_audio(response_text)
        except Exception as e:
            await ctx.send(f"TTS error: `{e}`")
            return

        source = FFmpegPCMAudio(audio_path)
        vc = ctx.voice_client
        if not vc:
            await ctx.send("Not connected to a voice channel.")
            return

        done = asyncio.Event()

        def _after_play(err: Exception | None):
            try:
                os.remove(audio_path)
            except Exception:
                pass
            done.set()

        # Only send 'Speaking…' message
        speaking_msg = await ctx.send("Speaking…")

        # Unmute before speaking
        if vc and hasattr(vc, "guild") and hasattr(vc, "mute"):
            try:
                await ctx.author.guild.me.edit(mute=False)
            except Exception:
                pass

        vc.play(source, after=_after_play)

        # Wait until finished
        while vc.is_playing():
            await asyncio.sleep(0.2)
        await done.wait()

        # Mute after speaking
        if vc and hasattr(vc, "guild") and hasattr(vc, "mute"):
            try:
                await ctx.author.guild.me.edit(mute=True)
            except Exception:
                pass

        # Delete 'Speaking…' message
        if speaking_msg:
            try:
                await speaking_msg.delete()
            except Exception:
                pass

        # Update lock timestamp (keeps ownership alive)
        lock["timestamp"] = _now().isoformat()
        self._write_lock(lock)

        # Listen for user leaving VC or AFK timeout
        async def check_user_left_or_afk():
            await asyncio.sleep(1)
            member = ctx.guild.get_member(ctx.author.id)
            if not member or not member.voice or member.voice.channel != channel:
                # User left VC
                try:
                    os.remove(self.lock_file)
                except Exception:
                    pass
                await ctx.send(f"{ctx.author.display_name} left the VC. Lock released. Next person can use the bot.")
                if vc and vc.is_connected():
                    await vc.disconnect()
        asyncio.create_task(check_user_left_or_afk())

    # ---------- Status ----------
    @commands.command(name="s_talkstatus")
    async def talk_status(self, ctx: commands.Context):
        lock = self._clear_if_expired(self._read_lock())
        if not lock:
            await ctx.send("No one is using the voice right now.")
            return
        uid = int(lock["user_id"])
        ts = datetime.fromisoformat(lock["timestamp"])
        elapsed = int((_now() - ts).total_seconds())
        member = ctx.guild.get_member(uid)
        name = member.display_name if member else f"<@{uid}>"
        remaining = max(0, 600 - elapsed)
        await ctx.send(f"{name} holds the voice lock. Auto-release in **{remaining} sec** if idle.")

    # ---------- Slash version ----------
    @app_commands.command(name="talk", description="Talk in your voice channel via TTS.")
    @app_commands.describe(message="What should I say?")
    async def slash_talk(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer(ephemeral=True, thinking=True)
        # create a lightweight context shim to reuse prefix logic
        class _ShimCtx:
            def __init__(self, bot, interaction):
                self.bot = bot
                self.guild = interaction.guild
                self.author = interaction.user
                self.voice_client = interaction.guild.voice_client if interaction.guild else None
                self.channel = interaction.channel

            async def send(self, content):
                await interaction.followup.send(content, ephemeral=True)

        ctx = _ShimCtx(self.bot, interaction)
        await self.talk_command.callback(self, ctx, message=message)  # call underlying impl

    # ---------- Ready ----------
    @commands.Cog.listener()
    async def on_ready(self):
        print("[BOT] TalkCommands ready.", flush=True)

    def _get_prefix(self, guild: Optional[discord.Guild]) -> str:
        default_prefix = "!s_"
        if not guild:
            return default_prefix
        # Always reload prefixes from config to ensure latest
        try:
            with open(os.path.join(os.path.dirname(__file__), "config.json"), "r", encoding="utf-8") as f:
                self.bot.prefixes = json.load(f)
        except Exception:
            self.bot.prefixes = {}
        return self.bot.prefixes.get(str(guild.id), default_prefix)


async def setup(bot: commands.Bot):
    await bot.add_cog(TalkCommands(bot))
