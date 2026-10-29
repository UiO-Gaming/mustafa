import asyncio
import datetime
import signal
from os import environ
from os import listdir
from os.path import realpath
from time import time
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

import aiohttp
import discord
import yaml
from discord.ext import commands
from psycopg_pool import AsyncConnectionPool

from cogs.utils import misc_utils
from cogs.utils.database import Database
from logger import BotLogger

DATABASE_RELIANT_COGS = {
    "birthday.py",
    "funreplies.py",
    "gullkorn.py",
    "mc_whitelist.py",
    "social_credit.py",
    "starboard_scraper.py",
    "streak.py",
    "user_facts.py",
    "word_cloud.py",
}
GALTINN_RELIANT_COGS = {"galtinn.py"}
SANITY_RELIANT_COGS = {"website_events.py"}
MINECRAFT_RELIANT_COGS = {"mc_whitelist.py"}


# Load config file
with open("./src/config/config.yaml", "r", encoding="utf8") as f:
    config = yaml.load(f, Loader=yaml.SafeLoader)


class Bot(commands.Bot):
    """UiO Gaming Bot"""

    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or(config["bot"]["prefix"]),
            case_insensitive=True,
            intents=discord.Intents.all(),
            allowed_mentions=discord.AllowedMentions(everyone=False),
        )

        self.logger = BotLogger().logger  # Initialize logger

        self.cog_files = set(listdir("./src/cogs"))

        # Check for missing credentials
        self.db_pool = None
        if self.check_credentials(config["database"], DATABASE_RELIANT_COGS):
            self.db_pool = AsyncConnectionPool(
                kwargs={
                    "host": config["database"]["host"],
                    "dbname": config["database"]["dbname"],
                    "user": config["database"]["username"],
                    "password": config["database"]["password"],
                    "autocommit": True,
                },
                configure=self.configure_db_connection,
                check=AsyncConnectionPool.check_connection,
                min_size=1,
                max_size=5,
                open=False,
            )
            self.db = Database(self.db_pool)

        if self.check_credentials(config["sanity"], SANITY_RELIANT_COGS):
            self.sanity = config["sanity"]

        if self.check_credentials(config["galtinn"], GALTINN_RELIANT_COGS):
            self.galtinn = config["galtinn"]

        if self.check_credentials(config["minecraft"], MINECRAFT_RELIANT_COGS):
            self.mc_rcon_password = config["minecraft"]["rcon_password"]

        # Fetch misc config values
        ids = config.get("ids") or {}
        self.UIO_GAMING_GUILD_ID = ids.get("guild")
        self.channel_ids = ids.get("channels") or {}
        self.role_ids = ids.get("roles") or {}
        self.user_ids = ids.get("users") or {}
        self.guild_id = config.get("dev_guild", self.UIO_GAMING_GUILD_ID)
        self.config_mode = config.get("config_mode")
        self.presence = config["bot"].get("presence", {})
        self.emoji = config.get("emoji", {})
        self.misc = config.get("misc", {})
        self.timezone = ZoneInfo(tz) if (tz := config.get("timezone")) else None  # None means the system timezone
        self.timezone_name = tz or self.system_timezone_name()

        try:
            midnight_tz = self.timezone or ZoneInfo(self.timezone_name)
        except (TypeError, ValueError, ZoneInfoNotFoundError):
            midnight_tz = datetime.UTC
        misc_utils.MIDNIGHT = datetime.time(tzinfo=midnight_tz)

    async def setup_hook(self):
        self.http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        if self.db_pool:
            await self.db_pool.open(wait=True, timeout=30)

        # Docker stops the container with SIGTERM. Close gracefully so cogs can save their caches
        try:
            asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(self.close()))
        except NotImplementedError:
            pass  # Not supported on Windows

        # Load cogs
        for file in self.cog_files:
            if file.endswith(".py"):
                name = file[:-3]
                await bot.load_extension(f"cogs.{name}")

        # Sync slash commands
        if self.config_mode == "prod":
            await self.tree.sync(guild=None)
        else:
            self.tree.copy_global_to(guild=discord.Object(id=self.guild_id))
            await self.tree.sync(guild=discord.Object(id=self.guild_id))

    async def close(self):
        await super().close()
        if hasattr(self, "http_session"):
            await self.http_session.close()
        if self.db_pool:
            await self.db_pool.close()

    async def configure_db_connection(self, conn):
        """
        Sets the session time zone of every new database connection to the bot's time zone
        """

        if self.timezone_name:
            await conn.execute("SELECT set_config('timezone', %s, false)", (self.timezone_name,))

    @staticmethod
    def system_timezone_name() -> str | None:
        """
        Get the IANA name of the system time zone

        Returns
        ----------
        (str | None): The time zone name. None if it can't be determined
        """

        if tz := environ.get("TZ"):
            return tz.removeprefix(":")

        localtime = realpath("/etc/localtime")
        if "/zoneinfo/" in localtime:
            return localtime.split("/zoneinfo/", 1)[1]

        return None

    def check_credentials(self, credentials: dict, dependant_cogs: set[str]) -> bool:
        """
        Check if the credentials are valid. Removes cogs from the class' `cog_files` attribute if not

        Parameters
        -----------
        credentials (dict): The credentials to check
        dependant_cogs (set): The cogs that depend on the credentials

        Returns
        ----------
        bool: Whether the credentials are valid. If not, the dependant cogs are disabled.
        """

        for credential in credentials.values():
            if not credential:
                self.logger.warning(f"Missing credentials. Disabling reliant cogs:\n{dependant_cogs}")
                self.cog_files -= dependant_cogs
                return False
        return True


# Create bot instance
bot = Bot()


@bot.event
async def on_ready():
    if not hasattr(bot, "uptime"):
        bot.uptime = time()

    # Print bot info
    print(f"Username:        {bot.user.name}")
    print(f"ID:              {bot.user.id}")
    print(f"Version:         {discord.__version__}")
    print("." * 50 + "\n")

    # Set initial presence
    # Presence status
    status_types = {
        "online": discord.Status.online,
        "dnd": discord.Status.dnd,
        "idle": discord.Status.idle,
        "offline": discord.Status.offline,
    }
    status_type = status_types.get(bot.presence["type"].lower(), discord.Status.online)

    # Presence actitivity
    activities = {"playing": 0, "listening": 2, "watching": 3}
    activity_type = activities.get(bot.presence["activity"].lower(), 0)

    await bot.change_presence(
        activity=discord.Activity(type=activity_type, name=bot.presence["message"]), status=status_type
    )


bot.run(config["bot"]["token"], reconnect=True, log_handler=None)
