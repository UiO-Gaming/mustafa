import random
import re
from dataclasses import dataclass
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from cogs.utils import embed_templates


@dataclass
class FunReply:
    """A reply the bot sends when a message matches its pattern"""

    name: str
    pattern: str
    reply: str
    chance: int = 100


@dataclass
class FunReplySettings:
    """Settings changed with /autosvar. None means the reply's default is used"""

    enabled: bool = True
    cooldown: int | None = None
    chance: int | None = None


DEFAULT_COOLDOWN = 600

# Only the first matching reply is sent, so the order matters
FUN_REPLIES = [
    FunReply("borgerlønn", r"(^|\W)borgerlønn(\W|$)", "@ sivert DE SNAKKER OM BORGERLØNN", chance=50),
    FunReply("olof palme", r"(^|\W)olof palme(\W|$)", "Jeg vet hvem som drepte Olof Palme 👀"),
    FunReply("yeet", r"(^|\W)+ye+et($|\W)+", "<:Nei:826593267642662912>"),
    FunReply(
        "drikke",
        r"(^|\W)skal? aldri drikke?[\w\s]*igjen($|\W)+",
        ":billed_cap:\nhttps://cdn.discordapp.com/attachments/811606213665357824/1320756460321378396/v15044gf0000ctk1refog65kh5pqtpkg.mov",
        chance=75,
    ),
    FunReply("sivert", r"(^|\W)(jeg?|(e|æ)(g|j)?|i) er? sivert arntzen($|\W)+", "Nei, jeg er Sivert Arntzen!"),
    FunReply(
        "bærum", r"(^|\W)bærum(\W|$)", "Sa noen Bærum? 👀🍾 <@205741213050077185> <@183635579483848705>", chance=50
    ),
    FunReply("ost", r"(^|\W)ost(\W|$)", "Lol, Robert ost🧀", chance=10),
]

FUN_REPLIES_BY_NAME = {fun_reply.name: fun_reply for fun_reply in FUN_REPLIES}
REPLY_CHOICES = [app_commands.Choice(name=fun_reply.name, value=fun_reply.name) for fun_reply in FUN_REPLIES]


class FunReplies(commands.Cog):
    """Reply to messages that trigger certain key words/phrases"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot
        self.settings: dict[str, FunReplySettings] = {}
        self.last_replied: dict[str, datetime] = {}

    async def cog_load(self):
        """
        Set up the database and load the reply settings before the cog is used
        """

        await self.init_db()

        rows = await self.bot.db.fetchall("SELECT name, enabled, cooldown, chance FROM fun_reply_settings")
        self.settings = {name: FunReplySettings(*values) for name, *values in rows}

    async def init_db(self):
        """
        Create the necessary tables for the funreplies cog to work
        """

        await self.bot.db.execute("""
            CREATE TABLE IF NOT EXISTS fun_reply_settings (
                name TEXT PRIMARY KEY,
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                cooldown INTEGER,
                chance INTEGER
            );
            """)

    def get_settings(self, name: str) -> FunReplySettings:
        """
        Get the settings of a fun reply, creating default settings if it has none

        Parameters
        ----------
        name (str): The name of the fun reply

        Returns
        ----------
        (FunReplySettings): The settings of the fun reply
        """

        return self.settings.setdefault(name, FunReplySettings())

    def get_cooldown(self, fun_reply: FunReply) -> int:
        """
        Get the cooldown of a fun reply in seconds

        Parameters
        ----------
        fun_reply (FunReply): The fun reply

        Returns
        ----------
        (int): The configured cooldown, or the default cooldown if none is set
        """

        cooldown = self.get_settings(fun_reply.name).cooldown
        return DEFAULT_COOLDOWN if cooldown is None else cooldown

    def get_chance(self, fun_reply: FunReply) -> int:
        """
        Get the chance of a fun reply being sent in percent

        Parameters
        ----------
        fun_reply (FunReply): The fun reply

        Returns
        ----------
        (int): The configured chance, or the reply's default chance if none is set
        """

        chance = self.get_settings(fun_reply.name).chance
        return fun_reply.chance if chance is None else chance

    async def save_settings(self, name: str):
        """
        Save the settings of a fun reply to the database

        Parameters
        ----------
        name (str): The name of the fun reply
        """

        settings = self.get_settings(name)
        await self.bot.db.execute(
            """
            INSERT INTO fun_reply_settings (name, enabled, cooldown, chance)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE
                SET enabled = EXCLUDED.enabled, cooldown = EXCLUDED.cooldown, chance = EXCLUDED.chance
            """,
            (name, settings.enabled, settings.cooldown, settings.chance),
        )

    @commands.Cog.listener("on_message")
    async def reply_to_triggers(self, message: discord.Message):
        """
        Replies to messages that trigger certain key words/phrases

        Parameters
        ----------
        message (discord.Message): The message to check for triggers
        """

        if message.author.bot:
            return

        for fun_reply in FUN_REPLIES:
            if await self.trigger(message, fun_reply):
                return

    async def trigger(self, message: discord.Message, fun_reply: FunReply) -> bool:
        """
        Send a fun reply if the message matches it and it is enabled, off cooldown and passes its chance roll

        Parameters
        ----------
        message (discord.Message): The message to check for triggers
        fun_reply (FunReply): The fun reply to check

        Returns
        ----------
        (bool): Whether or not the reply was triggered
        """

        settings = self.get_settings(fun_reply.name)
        if not settings.enabled:
            return False

        last_replied = self.last_replied.get(fun_reply.name)
        if last_replied and (discord.utils.utcnow() - last_replied).total_seconds() < self.get_cooldown(fun_reply):
            return False

        if re.search(fun_reply.pattern, message.content, flags=re.IGNORECASE) and random.randint(
            1, 100
        ) <= self.get_chance(fun_reply):
            await message.reply(fun_reply.reply)
            self.last_replied[fun_reply.name] = discord.utils.utcnow()
            return True

        return False

    fun_replies_group = app_commands.Group(
        name="autosvar",
        description="Skru automatiske svar av og på",
        guild_only=True,
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @fun_replies_group.command(name="av", description="Skru av et automatisk svar")
    @app_commands.rename(name="navn")
    @app_commands.describe(name="Navnet på svaret")
    @app_commands.choices(name=REPLY_CHOICES)
    async def disable(self, interaction: discord.Interaction, name: str):
        """
        Disable a fun reply

        Parameters
        ----------
        interaction (discord.Interaction): The slash command interaction
        name (str): The name of the fun reply
        """

        self.get_settings(name).enabled = False
        await self.save_settings(name)

        await interaction.response.send_message(embed=embed_templates.success(f"`{name}` er skrudd av"))

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @fun_replies_group.command(name="på", description="Skru på et automatisk svar")
    @app_commands.rename(name="navn")
    @app_commands.describe(name="Navnet på svaret")
    @app_commands.choices(name=REPLY_CHOICES)
    async def enable(self, interaction: discord.Interaction, name: str):
        """
        Enable a fun reply

        Parameters
        ----------
        interaction (discord.Interaction): The slash command interaction
        name (str): The name of the fun reply
        """

        self.get_settings(name).enabled = True
        await self.save_settings(name)

        await interaction.response.send_message(embed=embed_templates.success(f"`{name}` er skrudd på"))

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @fun_replies_group.command(name="nedkjøling", description="Sett hvor lenge et automatisk svar venter mellom svar")
    @app_commands.rename(name="navn", seconds="sekunder")
    @app_commands.describe(
        name="Navnet på svaret", seconds=f"Nedkjøling i sekunder. La stå tom for standard ({DEFAULT_COOLDOWN})"
    )
    @app_commands.choices(name=REPLY_CHOICES)
    async def set_cooldown(
        self, interaction: discord.Interaction, name: str, seconds: app_commands.Range[int, 0, 604800] | None = None
    ):
        """
        Set the cooldown of a fun reply

        Parameters
        ----------
        interaction (discord.Interaction): The slash command interaction
        name (str): The name of the fun reply
        seconds (int | None): The cooldown in seconds. None resets it to the default
        """

        self.get_settings(name).cooldown = seconds
        await self.save_settings(name)

        cooldown = self.get_cooldown(FUN_REPLIES_BY_NAME[name])
        await interaction.response.send_message(
            embed=embed_templates.success(f"`{name}` har nå {cooldown} sekunder nedkjøling")
        )

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @fun_replies_group.command(name="sjanse", description="Sett sjansen for at et automatisk svar blir sendt")
    @app_commands.rename(name="navn", percent="prosent")
    @app_commands.describe(name="Navnet på svaret", percent="Sjansen i prosent. La stå tom for standard")
    @app_commands.choices(name=REPLY_CHOICES)
    async def set_chance(
        self, interaction: discord.Interaction, name: str, percent: app_commands.Range[int, 0, 100] | None = None
    ):
        """
        Set the chance of a fun reply being sent

        Parameters
        ----------
        interaction (discord.Interaction): The slash command interaction
        name (str): The name of the fun reply
        percent (int | None): The chance in percent. None resets it to the default
        """

        self.get_settings(name).chance = percent
        await self.save_settings(name)

        chance = self.get_chance(FUN_REPLIES_BY_NAME[name])
        await interaction.response.send_message(embed=embed_templates.success(f"`{name}` har nå {chance} % sjanse"))

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @fun_replies_group.command(name="liste", description="Se innstillingene til de automatiske svarene")
    async def list_replies(self, interaction: discord.Interaction):
        """
        List all fun replies with their settings

        Parameters
        ----------
        interaction (discord.Interaction): The slash command interaction
        """

        lines = []
        for fun_reply in FUN_REPLIES:
            status = "✅" if self.get_settings(fun_reply.name).enabled else "❌"
            chance, cooldown = self.get_chance(fun_reply), self.get_cooldown(fun_reply)
            lines.append(f"{status} `{fun_reply.name}` · {chance} % · {cooldown} s")

        embed = discord.Embed(title="Automatiske svar", description="\n".join(lines))
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): The bot instance
    """

    await bot.add_cog(FunReplies(bot))
