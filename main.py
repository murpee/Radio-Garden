import discord
import os
import requests
from discord.ext import commands
from threading import Thread
from flask import Flask

# --- Port verification web helper for Railway uptime ---
app = Flask('')
@app.route('/')
def home():
    return "Radio Garden Bot is Online!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- Live Audio Stream Endpoint ---
URL_LISTEN = "https://radio.garden"

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True
bot = commands.Bot(command_prefix='`', intents=intents)

@bot.event
async def on_ready():
    print('We have logged in as {0.user}'.format(bot))

@bot.event
async def on_command_error(ctx, error):
    print("Command error:", error)
    await ctx.send(f"Something went wrong: {error}")

@bot.command(name="hello")
async def hello(ctx):
    await ctx.send("📻 Radio Garden bot is ready! Paste a link or ID to stream.")

@bot.command(name="play")
async def play(ctx, station_input: str = None):
    if not station_input:
        await ctx.send("Please provide a Radio Garden link, ID, or direct stream link!")
        return

    station_input = station_input.strip()
    
    # FIXED: Check if it's a universal stream link or a Radio Garden link
    if "radio.garden" in station_input or not station_input.startswith("http"):
        # Handle Radio Garden Inputs
        station_id = station_input
        if "radio.garden/listen/" in station_id:
            station_id = station_id.split("/listen/")[-1].split("?")[0]
            if "/" in station_id:
                station_id = station_id.split("/")[-1]
        elif "/" in station_id:
            station_id = station_id.split("/")[-1]
            
        await ctx.send(f"Connecting to Radio Garden stream ID: **{station_id}**...")
        stream_url = f"{URL_LISTEN}{station_id}/channel.mp3"
        ffmpeg_options = (
            "-reconnect 1 "
            "-reconnect_streamed 1 "
            "-reconnect_delay_max 5 "
            "-headers 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "Referer: https://radio.garden'"
        )
    else:
        # Handle Universal Direct Radio Stream Inputs
        await ctx.send(f"Connecting to direct audio stream link...")
        stream_url = station_input
        ffmpeg_options = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"

    vc = ctx.voice_client
    if vc is None:
        try:
            channel = ctx.author.voice.channel
        except AttributeError:
            await ctx.send("You need to enter a voice channel first so I can join you!")
            return
        vc = await channel.connect()

    if vc.is_playing() or vc.is_paused():
        vc.stop()

    try:
        source = discord.FFmpegPCMAudio(stream_url, before_options=ffmpeg_options)
        vc.play(source, after=lambda e: print(f"Player disconnect: {e}") if e else None)
        await ctx.send("🎶 **Streaming live audio successfully!**")
    except Exception as e:
        print("Playback process crash:", e)
        await ctx.send("Could not stream this station. Double-check your link or station ID format!")

@bot.command(name="stop")
async def stop_(ctx):
    vc = ctx.voice_client
    if vc and (vc.is_playing() or vc.is_paused()):
        vc.stop()
        await ctx.send("Stopped the stream broadcast.")
    else:
        await ctx.send("Nothing is currently playing.")

@bot.command(name="leave", aliases=['disconnect'])
async def leave_(ctx):
    vc = ctx.voice_client
    if vc:
        await vc.disconnect()
        await ctx.send("Left the voice channel.")
    else:
        await ctx.send("I'm not in a voice channel.")

if __name__ == "__main__":
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if token:
        t = Thread(target=run_web_server)
        t.start()
        bot.run(token)
else:
        print("Error: Set your DISCORD_BOT_TOKEN inside your environment variables.")
        
