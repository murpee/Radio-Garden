import discord
import json
import os
import urllib.request
import urllib.parse
import requests
from discord.ext import commands

# =====================================================================
# 🛠️ TERMUX FALLBACK PATCH FOR DISCORD'S MANDATORY VOICE PROTOCOL
# This forces the voice client to skip modern DAVE upgrades and connect
# directly via classic standard encryption channels.
# =====================================================================
import discord.voice_client
discord.voice_client.VoiceClient.supported_modes = [
    'xsalsa20_poly1305_lite', 
    'xsalsa20_poly1305_suffix', 
    'xsalsa20_poly1305'
]
# =====================================================================

URL_SEARCH = "http://radio.garden/api/search?q="
URL_LISTEN = "https://radio.garden/api/ara/content/listen/"

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
    print('Message Content Intent status:', bot.intents.message_content)

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
        with urllib.request.urlopen(query_url) as url:
            apiResults = json.loads(url.read())

        msg = "Showing results for query: " + str(apiResults["query"]) + "\n"
        results = apiResults["hits"]["hits"]

        global gResults
        gResults = [None]

        number = 1
        for result in results:
            if result["_source"]["type"] == "channel":
                msg += f'{number}. {result["_source"]["title"]}\n'
                msg += f'\t{result["_source"]["subtitle"]}\n\n'
                url_ = result["_source"]["url"]
                gResults.append(url_[-8:])
                number += 1

        print("Search results updated.")
        if printMsg:
            await ctx.send(msg[:2000])
        return True
    except Exception as e:
        print("Search error:", e)
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
async def play(ctx, *args):
    global gResults
    if not args:
        await ctx.send("Please provide a search term or station number.")
        return

    firstTerm = args[0]
    try:
        selected = int(firstTerm)
        if not gResults or selected >= len(gResults) or selected < 1:
            await ctx.send("That's not a valid result number. Try searching first.")
            return
    except ValueError:
        print("Searching and playing first result...")
        ok = await _search(ctx, " ".join(args), printMsg=False)
        if not ok or len(gResults) < 2:
            await ctx.send("No stations found for that search.")
            return
        selected = 1

    print("Playing index:", selected)
    try:
        x = requests.head(getListenURL(gResults[selected]), allow_redirects=True, timeout=10)
        stream_url = removeRGQueryString(x.url)
        await restartStream(ctx, stream_url)
    except Exception as e:
        print("Playback error:", e)
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
            await ctx.send("Hey buddy, you need to join a voice channel")
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
        print("Error: set the DISCORD_BOT_TOKEN environment variable before running this bot.")
    else:
        bot.run(token)
