import discord
import json
import os
import urllib.request
import urllib.parse
import requests
from discord.ext import commands
from threading import Thread
from flask import Flask

# --- Render/Railway Port Verification Server ---
app = Flask('')
@app.route('/')
def home():
    return "Bot is alive!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- Radio Garden Setup ---
URL_SEARCH = "https://radio.garden"
URL_LISTEN = "https://radio.garden"

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True
bot = commands.Bot(command_prefix='`', intents=intents)

gResults = []

def getListenURL(channelID):
    return URL_LISTEN + channelID + "/channel.mp3"

def removeRGQueryString(url):
    pos = url.find("?listening-from-radio-garden")
    if pos != -1:
        return url[:pos]
    return url

@bot.event
async def on_ready():
    print('We have logged in as {0.user}'.format(bot))

@bot.event
async def on_command_error(ctx, error):
    print("Command error:", error)
    await ctx.send(f"Something went wrong: {error}")

@bot.command(name="hello")
async def hello(ctx):
    await ctx.send("hello", delete_after=20)

@bot.command(name="quit")
async def quit_(ctx):
    await ctx.send("Shutting down...")
    await bot.close()

async def _search(ctx, searchTerms, printMsg=True):
    print("Searching for:", searchTerms)
    try:
        query_url = URL_SEARCH + urllib.parse.quote(searchTerms)
        
        req = urllib.request.Request(
            query_url, 
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://radio.garden'
            }
        )
        
        with urllib.request.urlopen(req) as url:
            apiResults = json.loads(url.read())

        if "hits" not in apiResults or "hits" not in apiResults["hits"]:
            if printMsg:
                await ctx.send("No stations found for that search.")
            return False

        results = apiResults["hits"]["hits"]
        msg = f"Showing results for query: {searchTerms}\n"

        global gResults
        gResults = [None]

        number = 1
        for result in results:
            source = result.get("_source", result)
            if source.get("type") == "channel":
                msg += f'{number}. {source.get("title")}\n'
                if source.get("subtitle"):
                    msg += f'\t{source.get("subtitle")}\n\n'
                else:
                    msg += '\n'
                
                url_ = source.get("url", "")
                if url_:
                    gResults.append(url_[-8:])
                    number += 1

        print("Search results updated.")
        if number == 1:
            if printMsg:
                await ctx.send("No channels found matching that term.")
            return False

        if printMsg:
            await ctx.send(msg[:2000])
        return True
    except Exception as e:
        print("Search error details:", e)
        if printMsg:
            await ctx.send("Sorry, I couldn't search radio.garden right now.")
        return False

@bot.command(name="search", aliases=['lookup'])
async def search(ctx, *args):
    if not args:
        await ctx.send("Please provide a search term, e.g. `search jazz`.")
        return
    await _search(ctx, " ".join(args), printMsg=True)

@bot.command(name="play")
async def play(ctx, *, search_query: str = None):
    global gResults
    if not search_query:
        await ctx.send("Please provide a search term or station number, e.g. `play jazz`.")
        return

    try:
        selected = int(search_query.strip())
        if not gResults or selected >= len(gResults) or selected < 1:
            await ctx.send("That's not a valid result number. Try running `search` first.")
            return
    except ValueError:
        print(f"Searching and playing top result for: {search_query}")
        ok = await _search(ctx, search_query, printMsg=False)
        if not ok or len(gResults) < 2:
            await ctx.send("No stations found for that search. Try another station name!")
            return
        selected = 1

    print("Playing index selection:", selected)
    try:
        stream_url_raw = getListenURL(gResults[selected])
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://radio.garden'
        }
        x = requests.head(stream_url_raw, headers=headers, allow_redirects=True, timeout=10)
        stream_url = removeRGQueryString(x.url)
        await restartStream(ctx, stream_url)
    except Exception as e:
        print("Stream connection failed:", e)
        await ctx.send("Could not stream this station.")

async def restartStream(ctx, url):
    vc = ctx.voice_client
    if vc is None:
        try:
            channel = ctx.author.voice.channel
        except AttributeError:
            await ctx.send("Join a voice channel first, or use `connect`.")
            return
        vc = await channel.connect()
    if vc.is_playing() or vc.is_paused():
        vc.stop()
    source = discord.FFmpegPCMAudio(url)
    vc.play(source, after=lambda e: print(f"Player error: {e}") if e else None)
    await ctx.send(f"Now streaming: {url}")

@bot.command(name="connect", aliases=['join'])
async def connect_(ctx, *, channel: discord.VoiceChannel = None):
    if not channel:
        try:
            channel = ctx.author.voice.channel
        except AttributeError:
            await ctx.send("Hey buddy, you need to join a voice channel first.")
            return

    vc = ctx.voice_client
    if vc:
        if vc.channel.id == channel.id:
            await ctx.send("I'm already in that voice channel.")
        else:
            await vc.move_to(channel)
            await ctx.send(f"Moved to {channel.name}.")
    else:
        await channel.connect()
        await ctx.send(f"Connected to {channel.name}.")

@bot.command(name="disconnect", aliases=['leave'])
async def disconnect_(ctx):
    vc = ctx.voice_client
    if vc:
        await vc.disconnect()
        await ctx.send("Disconnected.")
    else:
        await ctx.send("I'm not connected to a voice channel.")

@bot.command(name="stop")
async def stop_(ctx):
    vc = ctx.voice_client
    if vc and (vc.is_playing() or vc.is_paused()):
        vc.stop()
        await ctx.send("Stopped.")
    else:
        await ctx.send("Nothing is playing.")

if __name__ == "__main__":
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: set the DISCORD_BOT_TOKEN environment variable.")
    else:
        t = Thread(target=run_web_server)
        t.start()
        bot.run(token)
        
