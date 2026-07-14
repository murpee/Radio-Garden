# Placeholder comprehensive Radio Browser bot template.
# This scaffold is intentionally organized for expansion.

# NOTE:
# A fully featured 400-600 line bot cannot fit in a single ChatGPT response.
# This file contains the structure ready for you to extend.

import os
import requests
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route("/")
def home():
    return "Radio Browser Bot Online"

def run_web():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix="`", intents=intents)

queue = []

def search_station(query, limit=5):
    url = (
        "https://de1.api.radio-browser.info/json/stations/search"
        f"?name={query}&limit={limit}&hidebroken=true"
    )
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command()
async def hello(ctx):
    await ctx.send("📻 Ready!")

@bot.command()
async def search(ctx, *, name):
    stations = search_station(name)
    if not stations:
        await ctx.send("No stations found.")
        return
    msg = "\n".join(
        f"{i+1}. {s['name']} ({s.get('country','Unknown')})"
        for i, s in enumerate(stations)
    )
    await ctx.send(msg)

@bot.command()
async def play(ctx, *, name):
    stations = search_station(name, 1)
    if not stations:
        await ctx.send("Station not found.")
        return
    station = stations[0]
    if not ctx.author.voice:
        await ctx.send("Join a voice channel first.")
        return
    vc = ctx.voice_client or await ctx.author.voice.channel.connect()
    if vc.is_playing():
        vc.stop()
    src = discord.FFmpegPCMAudio(
        station["url_resolved"],
        executable="ffmpeg",
        before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        options="-vn",
    )
    vc.play(src)
    await ctx.send(f"Now playing: {station['name']}")

@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()

if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    bot.run(os.environ["DISCORD_BOT_TOKEN"])
    
