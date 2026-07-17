import os
import asyncio
import discord

# Automatically targets your specific channel environment layout
TARGET_VC_ID = 1522975909504749749  

intents = discord.Intents.default()
intents.voice_states = True

class SilenceSource(discord.AudioSource):
    def read(self):
        return b'\x00' * 384

class Auto247Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.vc_client = None

    async def on_ready(self):
        print(f"Logged in as {self.user.name} - Initializing Auto-Join Routine.")
        await self.connect_to_target()

    async def connect_to_target(self):
        channel = self.get_channel(TARGET_VC_ID)
        if not channel:
            print(f"CRITICAL: Could not find Voice Channel with ID {TARGET_VC_ID}")
            return

        try:
            print(f"Connecting directly to voice channel: {channel.name}")
            self.vc_client = await channel.connect(self_deaf=True)
            self.loop.create_task(self.keep_alive_loop())
        except Exception as e:
            print(f"Connection failed: {e}")

    async def keep_alive_loop(self):
        while self.vc_client and self.vc_client.is_connected():
            if not self.vc_client.is_playing():
                try:
                    self.vc_client.play(SilenceSource())
                except Exception:
                    pass
            await asyncio.sleep(1)

    async def on_voice_state_update(self, member, before, after):
        if member.id == self.user.id and after.channel is None:
            print("Server disconnected the bot. Triggering auto-reconnect...")
            if self.vc_client:
                try:
                    await self.vc_client.disconnect(force=True)
                except Exception:
                    pass
            await asyncio.sleep(3)
            await self.connect_to_target()

bot = Auto247Bot()
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("CRITICAL: DISCORD_TOKEN is missing from your host variables environment.")
    
