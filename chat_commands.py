from typing import Optional
import os
import json
import re
import asyncio
import discord
from discord.ext import commands

# ===== ChatCommands Cog =====
class ChatCommands(commands.Cog):
    """
    Text chat + intent router.
    - Replies in a fixed "bot channel" (if set), OR when mentioned / replied to.
    - Detects simple "voice" or "image" intents and routes appropriately.
    - Works with a provided shapes_client for LLM responses (optional).
    """

    def __init__(self, bot, shapes_client=None, model_name: Optional[str] = None):
        self.bot = bot
        self.shapes_client = shapes_client
        self.model_name = model_name or os.getenv("SHAPE_MODEL_NAME") or "shape-medium"
        print("[BOT] Chat_Commands Ready!", flush=True)

    # ---------- Helpers ----------
    @staticmethod
    def _config_path(name: str) -> str:
        return os.path.join(os.path.dirname(__file__), name)

    def _load_bot_channel(self) -> Optional[int]:
        try:
            with open(self._config_path("bot_channel.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("bot_channel_id")
        except Exception:
            return None

    def _save_bot_channel(self, channel_id: Optional[int]) -> None:
        with open(self._config_path("bot_channel.json"), "w", encoding="utf-8") as f:
            json.dump({"bot_channel_id": channel_id}, f, indent=2)

    def _get_prefix(self, guild: Optional[discord.Guild]) -> str:
        default_prefix = "!s_"
        if not guild:
            return default_prefix
        # Always reload prefixes from config to ensure latest
        try:
            with open(self._config_path("config.json"), "r", encoding="utf-8") as f:
                self.bot.prefixes = json.load(f)
        except Exception:
            self.bot.prefixes = {}
        return self.bot.prefixes.get(str(guild.id), default_prefix)

    # ---------- Help ----------
    @discord.app_commands.command(name="help", description="Show bot help.")
    async def slash_help(self, interaction: discord.Interaction):
        prefix = self._get_prefix(interaction.guild)
        embed = discord.Embed(title="Tara Bot Help", color=0xffc0cb)
        embed.add_field(name=f"{prefix}s_help", value="Show this help message", inline=False)
        embed.add_field(name=f"{prefix}s_talk <message>", value="Bot will join your VC and speak the message (one user at a time; auto-release after 10 minutes of inactivity).", inline=False)
        embed.add_field(name=f"{prefix}s_talkstatus", value="Check who is using the talk command and time remaining.", inline=False)
        embed.add_field(name=f"{prefix}s_setbotchannel", value="(Admin) Set this channel as the bot chat channel (bot replies to all messages here).", inline=False)
        embed.add_field(name=f"{prefix}s_unsetbotchannel", value="(Admin) Unset fixed bot chat channel (bot replies only to mentions/replies).", inline=False)
        embed.add_field(name=f"{prefix}setprefix <prefix>", value="(Admin) Change the bot's prefix for this server.", inline=False)
        embed.add_field(name="Mention or reply to the bot", value="Bot will reply in any text channel.", inline=False)
        embed.add_field(name=f"Image prompt (e.g. '{prefix}imagine a cute cat')", value="Bot will generate an image (if your backend supports it).", inline=False)
        embed.set_footer(text="TARA Bot | Powered by Shape & ElevenLabs (TTS)")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="s_help", aliases=["help"])
    async def help_command(self, ctx: commands.Context):
        # reuse the slash embed
        prefix = self._get_prefix(ctx.guild)
        embed = discord.Embed(title="Tara Bot Help", color=0xffc0cb)
        embed.add_field(name=f"{prefix}s_help", value="Show this help message", inline=False)
        embed.add_field(name=f"{prefix}s_talk <message>", value="Bot will join your VC and speak the message (one user at a time; auto-release after 10 minutes of inactivity).", inline=False)
        embed.add_field(name=f"{prefix}s_talkstatus", value="Check who is using the talk command and time remaining.", inline=False)
        embed.add_field(name=f"{prefix}s_setbotchannel", value="(Admin) Set this channel as the bot chat channel (bot replies to all messages here).", inline=False)
        embed.add_field(name=f"{prefix}s_unsetbotchannel", value="(Admin) Unset fixed bot chat channel (bot replies only to mentions/replies).", inline=False)
        embed.add_field(name=f"{prefix}setprefix <prefix>", value="(Admin) Change the bot's prefix for this server.", inline=False)
        embed.add_field(name="Mention or reply to the bot", value="Bot will reply in any text channel.", inline=False)
        embed.add_field(name=f"Image prompt (e.g. '{prefix}imagine a cute cat')", value="Bot will generate an image (if your backend supports it).", inline=False)
        embed.set_footer(text="TARA Bot | Powered by Shape & ElevenLabs (TTS)")
        await ctx.send(embed=embed)

    # ---------- Prefix management ----------
    @discord.app_commands.command(name="setprefix", description="(Admin) Change the bot's prefix for this server.")
    @discord.app_commands.describe(new_prefix="The new prefix to set (1-5 chars).")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def slash_setprefix(self, interaction: discord.Interaction, new_prefix: str):
        if not 1 <= len(new_prefix) <= 5:
            await interaction.response.send_message("Prefix length must be 1–5 characters.", ephemeral=True)
            return
        if not hasattr(self.bot, "prefixes"):
            self.bot.prefixes = {}
        self.bot.prefixes[str(interaction.guild.id)] = new_prefix
        await interaction.response.send_message(f"Prefix set to `{new_prefix}`", ephemeral=True)

    @commands.command(name="setprefix")
    @commands.has_permissions(administrator=True)
    async def setprefix_prefix(self, ctx: commands.Context, new_prefix: str):
        if not 1 <= len(new_prefix) <= 5:
            await ctx.send("Prefix length must be 1–5 characters.")
            return
        if not hasattr(self.bot, "prefixes"):
            self.bot.prefixes = {}
        self.bot.prefixes[str(ctx.guild.id)] = new_prefix
        await ctx.send(f"Prefix set to `{new_prefix}`")

    # ---------- Bot channel bind/unbind ----------
    @commands.command(name="s_setbotchannel")
    @commands.has_permissions(administrator=True)
    async def s_setbotchannel(self, ctx: commands.Context):
        self._save_bot_channel(ctx.channel.id)
        await ctx.send(f"Fixed bot chat channel set to {ctx.channel.mention}.")

    @commands.command(name="s_unsetbotchannel")
    @commands.has_permissions(administrator=True)
    async def s_unsetbotchannel(self, ctx: commands.Context):
        self._save_bot_channel(None)
        await ctx.send("Fixed bot chat channel cleared. I will reply only to mentions or replies.")

    @discord.app_commands.command(name="unsetbotchannel", description="(Admin) Remove the fixed bot chat channel.")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def slash_unsetbotchannel(self, interaction: discord.Interaction):
        bot = self.bot
        bot.bot_channel_id = None
        config_path = os.path.join(os.path.dirname(__file__), 'bot_channel.json')
        with open(config_path, 'w') as f:
            json.dump({'bot_channel_id': None}, f)
        await interaction.response.send_message("Fixed bot chat channel unset. Bot will now only reply to mentions and replies.", ephemeral=True)

    # ---------- Message listener ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # ignore bot/self
        if not message.guild or message.author.bot:
            return

        bot: commands.Bot = self.bot
        bot.bot_channel_id = self._load_bot_channel()

        def should_trigger() -> bool:
            if bot.bot_channel_id and message.channel.id == bot.bot_channel_id:
                return True
            if bot.user in message.mentions:
                return True
            if message.reference and getattr(message.reference, "resolved", None) and getattr(message.reference.resolved, "author", None) == bot.user:
                return True
            return False

        if not should_trigger():
            return

        # Prevent feedback loops with prefix commands; let command processor run
        ctx = await bot.get_context(message)
        if ctx.valid:
            return

        async with message.channel.typing():
            await asyncio.sleep(0.5)
            response = await self.chat_with_bot(message.content)

        # Route to Talk if voice intent
        if isinstance(response, dict) and response.get("type") == "voice":
            talk_cog = bot.get_cog("TalkCommands")
            if talk_cog:
                ctx = await bot.get_context(message)
                # call the prefix command implementation directly
                await talk_cog.talk_command(ctx, message=message.content)
            else:
                await message.channel.send("Voice module is not loaded. Ask the admin to load `talk_commands`.")
            return

        # Image intent -> send URL or text fallback
        if isinstance(response, dict) and response.get("type") == "image":
            url = response.get("url")
            if url:
                await message.channel.send(url)
            else:
                await message.channel.send(response.get("text") or "I tried to create an image but couldn't.")
            return

        # Plain text
        if isinstance(response, str):
            await message.channel.send(response)
        elif isinstance(response, dict) and "text" in response:
            await message.channel.send(response["text"])
        else:
            await message.channel.send("Sorry, I couldn't understand that.")

    # ---------- LLM call + simple intent detection ----------
    async def chat_with_bot(self, message: str):
        """
        Returns:
          - {'type':'voice'} to route to VC talk
          - {'type':'image','url':...} or {'type':'image','text':...}
          - plain text string
        """
        # voice keywords
        if re.search(r"\b(say this|read this|speak this|use voice|voice mode|talk in vc)\b", message, re.I):
            return {"type": "voice"}

        # image keywords (keep conservative)
        img_match = re.search(r"^(?:!imagine\s+)?(?:imagine|draw|paint|sketch|generate|make)\s+(.*)", message, re.I)
        if img_match:
            prompt = img_match.group(1).strip()
            # If you have an image backend, call it here and return URL.
            return {"type": "image", "text": f"(Image request noted) Prompt: {prompt}"}

        # Call Shapes client if provided
        if self.shapes_client:
            try:
                # Example Shape SDK call; adjust to your client API
                reply = self.shapes_client.chat(self.model_name, message)
                if isinstance(reply, str):
                    return reply
                if isinstance(reply, dict) and "text" in reply:
                    return reply["text"]
            except Exception as e:
                return f"Shape error: {e!r}"

        # Fallback local echo
        return f"You said: {message}"

    # ---------- Lifecycle ----------
    @commands.Cog.listener()
    async def on_ready(self):
        try:
            await self.bot.tree.sync()
        except Exception:
            pass
        print("[BOT] ChatCommands ready & slash commands synced.", flush=True)


async def setup(bot: commands.Bot):
    """
    Only add ChatCommands here.
    (TalkCommands must be in talk_commands.py)
    """
    # If you build the bot elsewhere, pass shapes_client & model_name via bot attrs:
    shapes_client = getattr(bot, "shapes_client", None)
    model_name = getattr(bot, "shape_model_name", None)
    await bot.add_cog(ChatCommands(bot, shapes_client, model_name))
