import os
import asyncio
import discord
from discord.ext import commands, tasks

intents = discord.Intents.default()
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

TOKEN = os.getenv("DISCORD_TOKEN")
VC_ID = 1522975872959774912

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    if not keep_vc_alive.is_running():
        keep_vc_alive.start()

@tasks.loop(seconds=20)
async def keep_vc_alive():
    channel = bot.get_channel(VC_ID)
    if not channel:
        print("Voice channel not found. Check your VOICE_CHANNEL_ID.")
        return

    vc = discord.utils.get(bot.voice_clients, guild=channel.guild)
    
    if not vc:
        try:
            vc = await channel.connect(timeout=20.0, reconnect=True)
            print(f"Connected to {channel.name}")
            await asyncio.sleep(2)  # Critical 2-second stabilization delay
        except Exception as e:
            print(f"Failed to connect: {e}")
            return

    if vc and vc.is_connected() and not vc.is_playing():
        try:
            source = discord.FFmpegPCMAudio("https://github.com")
            vc.play(source)
        except Exception as e:
            print(f"Audio playback error: {e}")

bot.run(TOKEN)
