import os
import asyncio
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

is_247_enabled = False
target_voice_channel_id = None

class SilenceAudio(discord.AudioSource):
    """Generates continuous raw silence packets to bypass Discord's idle kick."""
    def read(self):
        return b'\x00' * 384

async def keep_vc_alive(vc_client):
    """Feeds silence to the voice gateway to make the bot look active."""
    while is_247_enabled and vc_client.is_connected():
        if not vc_client.is_playing():
            try:
                vc_client.play(SilenceAudio())
            except Exception:
                pass
        await asyncio.sleep(1)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} - 24/7 Voice Core Active.")

@bot.event
async def on_voice_state_update(member, before, after):
    """Listens for random server drops or kicks and forces a clean rejoin."""
    global is_247_enabled, target_voice_channel_id
    
    if member.id == bot.user.id and is_247_enabled:
        # If the bot was disconnected from its target channel
        if after.channel is None:
            print("Detected disconnect. Cleaning up session...")
            
            # Force clean the old broken session state on our side
            if member.guild.voice_client:
                try:
                    await member.guild.voice_client.disconnect(force=True)
                except Exception:
                    pass
            
            await asyncio.sleep(3)  # Give Discord gateway time to reset
            
            print("Reconnecting to target VC cleanly...")
            channel = bot.get_channel(target_voice_channel_id)
            if channel:
                try:
                    vc = await channel.connect(self_deaf=True)
                    bot.loop.create_task(keep_vc_alive(vc))
                except Exception as e:
                    print(f"Clean reconnection error: {e}")

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
        
        # Clear any ghost connections before joining
        if ctx.voice_client:
            await ctx.voice_client.disconnect(force=True)
            await asyncio.sleep(1)
            
        vc = await channel.connect(self_deaf=True)
        bot.loop.create_task(keep_vc_alive(vc))
        await ctx.send(f"✅ **24/7 Mode Activated.** Locked into `{channel.name}`.")
    else:
        is_247_enabled = False
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        await ctx.send("🛑 **24/7 Mode Deactivated.** Leaving channel.")

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("CRITICAL: DISCORD_TOKEN is missing from your host variables environment.")
    
