import os
import asyncio
import discord
from discord.ext import commands

# Step 1: Set up gateway intents for tracking channel states
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# State management variables
is_247_enabled = False
target_voice_channel_id = None

class SilenceAudio(discord.AudioSource):
    """Generates continuous raw silence packets to bypass Discord's idle kick."""
    def read(self):
        # 20ms of empty raw PCM sound data
        return b'\x00' * 384

async def keep_vc_alive(vc_client):
    """Feeds silence to the voice gateway to make the bot look active."""
    while is_247_enabled and vc_client.is_connected():
        if not vc_client.is_playing():
            vc_client.play(SilenceAudio())
        await asyncio.sleep(1)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} - 24/7 Voice Core Active.")

@bot.event
async def on_voice_state_update(member, before, after):
    """Listens for random server drops or kicks and forces an instant rejoin."""
    global is_247_enabled, target_voice_channel_id
    
    if member.id == bot.user.id and is_247_enabled:
        if after.channel is None: # Bot was disconnected
            print("Detected disconnect. Reconnecting to target VC instantly...")
            channel = bot.get_channel(target_voice_channel_id)
            if channel:
                try:
                    vc = await channel.connect(self_deaf=True)
                    bot.loop.create_task(keep_vc_alive(vc))
                except Exception as e:
                    print(f"Reconnection error: {e}")

@bot.command()
async def join247(ctx):
    """Locks the bot into your current voice channel indefinitely."""
    global is_247_enabled, target_voice_channel_id
    
    if not ctx.author.voice:
        return await ctx.send("❌ You must join a voice channel first!")
    
    channel = ctx.author.voice.channel
    target_voice_channel_id = channel.id
    
    if not is_247_enabled:
        is_247_enabled = True
        # Server deafen the bot to drastically minimize your hosting resource usage
        vc = await channel.connect(self_deaf=True)
        bot.loop.create_task(keep_vc_alive(vc))
        await ctx.send(f"✅ **24/7 Mode Activated.** Sitting in `{channel.name}`.")
    else:
        is_247_enabled = False
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        await ctx.send("🛑 **24/7 Mode Deactivated.** Leaving channel.")

# Pulls your deployment variable securely from Railway
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("CRITICAL: DISCORD_TOKEN is missing from your host variables environment.")
    
