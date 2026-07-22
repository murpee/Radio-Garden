import os
import asyncio
import logging
import discord

# --- Configuration ---
TARGET_VC_ID = 1522975909504749749
RECONNECT_BASE_DELAY = 3       # seconds before first retry
RECONNECT_MAX_DELAY = 60       # cap backoff at 60 seconds
RECONNECT_MAX_ATTEMPTS = 10    # retries per disconnect event
WATCHDOG_INTERVAL = 10         # how often (seconds) watchdog checks connection
SILENCE_INTERVAL = 1           # how often (seconds) keep_alive checks playback

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("Auto247Bot")

# --- Intents ---
intents = discord.Intents.default()
intents.voice_states = True


# --- Silence Audio Source ---
class SilenceSource(discord.AudioSource):
    """Streams silence (opus-safe PCM zeros) to keep the voice connection alive."""
    def read(self):
        return b"\x00" * 3840  # Increased frame size for stability

    def is_opus(self):
        return False


# --- Bot ---
class Auto247Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.vc_client = None
        self._reconnecting = False        # Prevent overlapping reconnect attempts
        self._watchdog_task = None
        self._keepalive_task = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def on_ready(self):
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        log.info("Starting initial connection to voice channel...")
        await self.connect_to_target()

    # ------------------------------------------------------------------
    # Voice Connection
    # ------------------------------------------------------------------

    async def connect_to_target(self):
        """Attempt to connect to the target VC with exponential backoff retries."""
        if self._reconnecting:
            log.warning("Reconnect already in progress — skipping duplicate call.")
            return

        self._reconnecting = True
        attempt = 0
        delay = RECONNECT_BASE_DELAY

        while attempt < RECONNECT_MAX_ATTEMPTS:
            attempt += 1
            log.info(f"Connection attempt {attempt}/{RECONNECT_MAX_ATTEMPTS}...")

            try:
                channel = self.get_channel(TARGET_VC_ID)

                if channel is None:
                    log.error(
                        f"Voice channel ID {TARGET_VC_ID} not found. "
                        "Check the ID and make sure the bot is in the server."
                    )
                    # No point retrying if the channel doesn't exist
                    self._reconnecting = False
                    return

                # Clean up any stale connection first
                await self._teardown_voice()

                log.info(f"Connecting to: #{channel.name} in '{channel.guild.name}'")
                self.vc_client = await channel.connect(
                    self_deaf=True,
                    reconnect=True,   # Let discord.py handle low-level reconnects
                    timeout=30.0,
                )

                log.info("Successfully connected to voice channel.")
                self._reconnecting = False

                # Restart background tasks
                self._start_background_tasks()
                return

            except discord.errors.ClientException as e:
                log.warning(f"ClientException on attempt {attempt}: {e}")
            except discord.errors.ConnectionClosed as e:
                log.warning(f"ConnectionClosed on attempt {attempt}: code={e.code}")
            except asyncio.TimeoutError:
                log.warning(f"Connection timed out on attempt {attempt}.")
            except Exception as e:
                log.error(f"Unexpected error on attempt {attempt}: {type(e).__name__}: {e}")

            if attempt < RECONNECT_MAX_ATTEMPTS:
                log.info(f"Retrying in {delay}s...")
                await asyncio.sleep(delay)
                delay = min(delay * 2, RECONNECT_MAX_DELAY)  # Exponential backoff

        log.critical(
            f"All {RECONNECT_MAX_ATTEMPTS} connection attempts failed. "
            "Bot will wait for the next disconnect event to retry."
        )
        self._reconnecting = False

    async def _teardown_voice(self):
        """Safely disconnect and clean up any existing voice client."""
        if self.vc_client is not None:
            try:
                if self.vc_client.is_playing():
                    self.vc_client.stop()
                if self.vc_client.is_connected():
                    await self.vc_client.disconnect(force=True)
            except Exception as e:
                log.warning(f"Error during voice teardown (safe to ignore): {e}")
            finally:
                self.vc_client = None

    # ------------------------------------------------------------------
    # Background Tasks
    # ------------------------------------------------------------------

    def _start_background_tasks(self):
        """Cancel old tasks and launch fresh ones after a successful connect."""
        for task in (self._watchdog_task, self._keepalive_task):
            if task and not task.done():
                task.cancel()

        self._keepalive_task = self.loop.create_task(self._keep_alive_loop())
        self._watchdog_task = self.loop.create_task(self._watchdog_loop())
        log.info("Background tasks started (keep-alive + watchdog).")

    async def _keep_alive_loop(self):
        """
        Continuously plays silence to prevent Discord from marking
        the bot as idle and disconnecting it.
        """
        log.info("Keep-alive loop running.")
        while True:
            try:
                if self.vc_client and self.vc_client.is_connected():
                    if not self.vc_client.is_playing():
                        self.vc_client.play(SilenceSource())
                await asyncio.sleep(SILENCE_INTERVAL)
            except asyncio.CancelledError:
                log.info("Keep-alive loop cancelled.")
                break
            except Exception as e:
                log.warning(f"Keep-alive error (non-fatal): {e}")
                await asyncio.sleep(SILENCE_INTERVAL)

    async def _watchdog_loop(self):
        """
        Independent watchdog that monitors the voice connection.
        If it detects a broken/missing connection that on_voice_state_update
        might have missed, it triggers a reconnect.
        """
        log.info("Watchdog loop running.")
        while True:
            try:
                await asyncio.sleep(WATCHDOG_INTERVAL)

                vc = self.vc_client
                if vc is None or not vc.is_connected():
                    if not self._reconnecting:
                        log.warning(
                            "Watchdog detected a dead voice connection. "
                            "Triggering reconnect..."
                        )
                        await self.connect_to_target()

            except asyncio.CancelledError:
                log.info("Watchdog loop cancelled.")
                break
            except Exception as e:
                log.error(f"Watchdog error: {e}")

    # ------------------------------------------------------------------
    # Discord Events
    # ------------------------------------------------------------------

    async def on_voice_state_update(self, member, before, after):
        """Catch Discord-initiated disconnects and reconnect immediately."""
        if member.id != self.user.id:
            return

        # Bot was moved to a different channel — update our reference
        if before.channel and after.channel and before.channel != after.channel:
            log.info(f"Bot was moved to #{after.channel.name}. Updating reference.")
            return

        # Bot was disconnected from voice entirely
        if before.channel is not None and after.channel is None:
            log.warning(
                f"Bot was disconnected from #{before.channel.name}. "
                "Initiating reconnect sequence..."
            )
            await asyncio.sleep(2)  # Brief pause before reconnecting
            await self.connect_to_target()

    async def on_error(self, event, *args, **kwargs):
        log.error(f"Unhandled error in event '{event}'", exc_info=True)


# ------------------------------------------------------------------
# Entry Point
# ------------------------------------------------------------------

bot = Auto247Bot()
TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN:
    bot.run(TOKEN, log_handler=None)  # We handle our own logging
else:
    log.critical(
        "DISCORD_TOKEN is not set in your environment variables. "
        "Set it and restart the bot."
    )
    
