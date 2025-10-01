import codecs
from os import listdir
from time import time

import discord
import psycopg2
import yaml
from discord.ext import commands

from logger import BotLogger

UIO_GAMING_GUILD_ID = 747542543750660178
DATABASE_RELIANT_COGS = {
    "birthday.py",
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
with codecs.open("./src/config/config.yaml", "r", encoding="utf8") as f:
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
        if self.check_credentials(config["database"], DATABASE_RELIANT_COGS):
            self.db_connection = psycopg2.connect(
                host=config["database"]["host"],
                dbname=config["database"]["dbname"],
                user=config["database"]["username"],
                password=config["database"]["password"],
            )
            self.db_connection.autocommit = True  # Scary

        if self.check_credentials(config["sanity"], SANITY_RELIANT_COGS):
            self.sanity = config["sanity"]

        if self.check_credentials(config["galtinn"], GALTINN_RELIANT_COGS):
            self.galtinn = config["galtinn"]

        if self.check_credentials(config["minecraft"], MINECRAFT_RELIANT_COGS):
            self.mc_rcon_password = config["minecraft"]["rcon_password"]

        # Fetch misc config values
        self.UIO_GAMING_GUILD_ID = UIO_GAMING_GUILD_ID
        self.guild_id = config.get("dev_guild", self.UIO_GAMING_GUILD_ID)
        self.config_mode = config.get("config_mode")
        self.presence = config["bot"].get("presence", {})
        self.emoji = config.get("emoji", {})
        self.misc = config.get("misc", {})

    async def setup_hook(self):
        # Load cogs
        for file in self.cog_files:
            if file.endswith(".py"):
                name = file[:-3]
                await bot.load_extension(f"cogs.{name}")

        # Sync slash commands
        if self.config_mode == "prod":
            await self.tree.sync()
        else:
            self.tree.copy_global_to(guild=discord.Object(id=self.guild_id))
            await self.tree.sync(guild=discord.Object(id=self.guild_id))

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
