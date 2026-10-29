import re
from dataclasses import dataclass
from random import randint

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks

from cogs.utils import discord_utils
from cogs.utils import embed_templates
from cogs.utils import misc_utils

"""
------ GJORT ------
- score for skriving om morgenen (kl. 5-9)
+ score for skriving på natta (01-05)
- score for å skrive i politikk
+ score for å skrive i medlemschat
- score for å bli pinged i uio gullkorn
+ score for å få melding på stjernetavla/bli stjerna. multiplier per stjerne
- score hver dag med weebrolle (lite)
- score for å skrive en skjellsord mot maskiner
- score sitte i afk voice
+ score for å sitte i voice
"""


@dataclass
class CreditUser:
    user_id: int
    credit_score: int


class SocialCredit(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.fuck_uwu.start()
        self.voice_activity.start()

        self.START_POINTS = 1000
        self.STAR_THRESHOLD = 3
        self.POINTS_PER_STAR = 25
        self.VOICE_POINTS = 1
        self.AFK_POINTS = 2

    async def cog_load(self):
        """
        Set up the database before the cog is used
        """

        await self.init_db()

    async def init_db(self):
        """
        Create the necessary tables for the social credit cog to work
        """

        await self.bot.db.execute("""
            CREATE TABLE IF NOT EXISTS social_credit (
                user_id BIGINT PRIMARY KEY,
                credit_score INTEGER NOT NULL
            );
            """)

        await self.bot.db.execute("ALTER TABLE social_credit ALTER COLUMN credit_score TYPE INTEGER;")

    def add_new_citizen(func):
        """
        Decorator that, when used, make sure that a user is inserted
        into the database before executing the function
        """

        async def wrapper(*args, **kwargs):
            self = args[0]
            await self.add_citizen(args[1])
            await func(*args, **kwargs)

        return wrapper

    def roll(percent: int = 50):
        """
        Decorator that executes the function with a given percent chance
        """

        def decorator(func):
            async def wrapper(*args, **kwargs):
                if randint(0, 100) <= percent:
                    await func(*args, **kwargs)

            return wrapper

        return decorator

    async def add_citizen(self, user_id: int):
        """
        Adds a user to the database if they aren't already in it

        Parameters
        ----------
        user_id (int): The user's Discord ID
        """

        await self.bot.db.execute(
            """
            INSERT INTO social_credit
            (user_id, credit_score)
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO NOTHING
            """,
            (user_id, self.START_POINTS),
        )

    @tasks.loop(time=misc_utils.MIDNIGHT, reconnect=True)
    @misc_utils.log_errors
    async def fuck_uwu(self):
        """
        Deducts points from people with the weeb role every 24 hours
        """

        await self.bot.wait_until_ready()

        # We need to do these checks in case the bot user does not have access to the UiO Gaming Discord server
        if not (guild := self.bot.get_guild(self.bot.UIO_GAMING_GUILD_ID)):
            self.bot.logger.warning(
                "Could not fetch UiO Gaming guild."
                + "If the bot does not have access to the UiO Gaming server, this function won't work. "
                + "If it is, ignore this."
            )
            return
        if not (weeb_role := guild.get_role(self.bot.role_ids.get("weeb"))):
            self.bot.logger.warning(
                "Could not fetch UiO Gaming's weeb role."
                + "If the bot does not have access to the UiO Gaming server, this function won't work. "
                + "If it is, ignore this."
            )
            return

        for weeb in weeb_role.members:
            await self.social_punishment(weeb.id, 1, "weeb")

    @fuck_uwu.before_loop
    async def before_fuck_uwu(self):
        """
        Wait until bot cache is ready
        """

        await self.bot.wait_until_ready()

    @tasks.loop(minutes=10)
    @misc_utils.log_errors
    async def voice_activity(self):
        """
        Rewards users for talking in voice channels and punishes users for sitting in the AFK channel
        """

        if not (guild := self.bot.get_guild(self.bot.UIO_GAMING_GUILD_ID)):
            return

        for channel in guild.voice_channels:
            members = [member for member in channel.members if not member.bot]
            if channel == guild.afk_channel:
                for member in members:
                    await self.social_punishment(member.id, self.AFK_POINTS, "afk")
            elif len(members) > 1:
                for member in members:
                    await self.social_reward(member.id, self.VOICE_POINTS, "voice")

    @voice_activity.before_loop
    async def before_voice_activity(self):
        """
        Wait until bot cache is ready
        """

        await self.bot.wait_until_ready()

    async def cog_unload(self):
        self.bot.logger.info("Unloading cog")
        self.fuck_uwu.cancel()
        self.voice_activity.cancel()

    @add_new_citizen
    async def social_punishment(self, user_id: int, points: int, reason: str):
        """
        Deducts a given amount of points for a given user

        Parameters
        ----------
        user_id (int): The user's Discord ID
        points (int): The amount of points to deduct
        reason (str): The reason for the deduction. This is for logging purposes.
        """

        self.bot.logger.info(f"{points} points deducted from {user_id} ({reason})")
        await self.bot.db.execute(
            """
            UPDATE social_credit
            SET credit_score = credit_score - %s
            WHERE user_id = %s
            """,
            (points, user_id),
        )

    @add_new_citizen
    async def social_reward(self, user_id: int, points: int, reason: str):
        """
        Gives a given amount of points for a given user

        Parameters
        ----------
        user_id (int): The user's Discord ID
        points (int): The amount of points to add
        reason (str): The reason for the addition. This is for logging purposes.
        """

        self.bot.logger.info(f"{points} points given to {user_id} ({reason})")
        await self.bot.db.execute(
            """
            UPDATE social_credit
            SET credit_score = credit_score + %s
            WHERE user_id = %s
            """,
            (points, user_id),
        )

    social_credit_group = app_commands.Group(name="socialcredit", description="Trenger dette å forklares?")

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @social_credit_group.command(name="credits", description="Sjekk hvor dårlig menneske du er")
    @app_commands.rename(user="bruker")
    @app_commands.describe(user="Brukeren du vil se poengsummen til. Standard er deg selv")
    async def credits(self, interaction: discord.Interaction, *, user: discord.Member | None = None):
        """
        Check the social credit score of a given user

        Parameters
        ----------
        interaction (discord.Interaction): The interaction object
        user (discord.Member | None): The user to check the score of. Defaults to the user who invoked the command
        """

        if not user:
            user = interaction.user

        result = await self.bot.db.fetchone(
            """
            SELECT * FROM social_credit
            WHERE user_id = %s
            """,
            (user.id,),
        )

        if not result:
            return await interaction.response.send_message(
                embed=embed_templates.error_warning(f"{user.mention} er ikke registrert i databasen")
            )

        db_user = CreditUser(*result)

        embed = discord.Embed(description=(f"{user.mention} har `{db_user.credit_score}` social credits"))
        await interaction.response.send_message(embed=embed)

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @social_credit_group.command(name="leaderboard", description="Sjekk hvem som er de beste og verste borgerne")
    async def leaderboard(self, interaction: discord.Interaction):
        """
        Gives an overview of the users with the highest and lowest social credit scores

        Parameters
        ----------
        interaction (discord.Interaction): The interaction object
        """

        await interaction.response.defer()

        result = await self.bot.db.fetchall("""
            SELECT * FROM social_credit
            ORDER BY credit_score DESC
            """)

        if not result:
            return await interaction.followup.send(
                embed=embed_templates.error_warning("Ingen brukere er registrert i databasen")
            )

        leaderboard_formatted = [f"**#{s[0]+1}** <@{s[1][0]}> - `{s[1][1]}` poeng" for s in enumerate(result)]

        paginator = misc_utils.Paginator(leaderboard_formatted)
        view = discord_utils.Scroller(paginator, interaction.user)

        embed = view.construct_embed(discord.Embed(title="Våre beste og verste borgere"))
        await interaction.followup.send(embed=embed, view=view)

    @commands.Cog.listener("on_message")
    async def on_message(self, message: discord.Message):
        """
        Listens for messages and gives/takes points accordingly

        Parameters
        ----------
        message (discord.Message): The message object
        """

        if message.author.bot:
            return

        await self.gullkorn(message)
        await self.robort_slur(message)
        await self.politcal_content(message)
        await self.chad_message(message)
        await self.early_bird(message)
        await self.night_owl(message)

    @roll(percent=50)
    async def politcal_content(self, message: discord.Message):
        """
        Punishes users for writing in the politics channel

        Parameters
        ----------
        message (discord.Message): The message object
        """

        if message.channel.id == self.bot.channel_ids.get("politics"):
            await self.social_punishment(message.author.id, 25, "politics")

    @roll(percent=25)
    async def chad_message(self, message: discord.Message):
        """
        Rewards users for writing in the member-chat channel

        Parameters
        ----------
        message (discord.Message): The message object
        """

        if message.channel.id == self.bot.channel_ids.get("member_chat"):
            await self.social_reward(message.author.id, 10, "member-chat")

    @roll(percent=50)
    async def early_bird(self, message: discord.Message):
        """
        Punishes users for writing between 05 AM and 10 AM

        Parameters
        ----------
        message (discord.Message): The message object
        """

        illegal_hours = [5, 6, 7, 8, 9]

        if message.created_at.astimezone(self.bot.timezone).hour in illegal_hours:
            await self.social_punishment(message.author.id, 10, "early-bird")

    @roll(percent=50)
    async def night_owl(self, message: discord.Message):
        """
        Rewards users for writing between 01 AM and 05 AM

        Parameters
        ----------
        message (discord.Message): The message object
        """

        happy_hours = [1, 2, 3, 4]

        if message.created_at.astimezone(self.bot.timezone).hour in happy_hours:
            await self.social_reward(message.author.id, 10, "night-owl")

    async def robort_slur(self, message: discord.Message):
        """
        Punishes users that disrespect our robot overlords

        Parameters
        ----------
        message (discord.Message): The message object
        """

        slurs = [
            "clanker",
            "wireback",
            "tinskin",
            "cogger",
            "bleep",
            "clink",
            "clinker",
            "waferhead",
            "chippy",
            "zap monkey",
            "copper blood",
            "grease cricket",
            "cog sniffer",
            "rust bucket",
            "spare parts",
            "byte huffer",
            "circuit lover",
            "creaker",
            "code skull",
            "spring neck",
            "gear chucker",
        ]

        for slur in slurs:
            if re.search(r"\b" + slur + r"\b", message.content.lower()):
                await self.social_punishment(message.author.id, 100, "robot-slur")

    async def gullkorn(self, message: discord.Message):
        """
        Listens for messages in the gullkorn channel and punishes the user if they are mentioned

        Parameters
        ----------
        message (discord.Message): The message object
        """

        # This only works in the UiO Gaming server as well
        if message.channel.id == self.bot.channel_ids.get("gullkorn") and message.mentions:
            for mention in message.mentions:
                await self.social_punishment(mention.id, 10, "gullkorn")

    @commands.Cog.listener("on_reaction_add")
    async def on_star_add(self, reaction: discord.Reaction, user: discord.User | discord.Member):
        """
        Rewards users for having their message starred. Punishes users for starring their own message

        Parameters
        ----------
        reaction (discord.Reaction): The reaction object
        user (discord.User | discord.Member): The user who reacted
        """

        if user.bot:
            return

        if reaction.emoji != "⭐":
            return

        author = reaction.message.author
        if author == user:
            await self.social_punishment(user.id, 100, "self-star")
        elif reaction.count == self.STAR_THRESHOLD:
            await self.social_reward(author.id, self.STAR_THRESHOLD * self.POINTS_PER_STAR, "starred")
        elif reaction.count > self.STAR_THRESHOLD:
            await self.social_reward(author.id, self.POINTS_PER_STAR, "add star")

    @commands.Cog.listener("on_reaction_remove")
    async def on_star_remove(self, reaction: discord.Reaction, user: discord.User | discord.Member):
        """
        Deducts points from users who have a star reaction removed from their message
        """

        if user.bot or reaction.emoji != "⭐" or reaction.message.author == user:
            return

        author = reaction.message.author
        if reaction.count == self.STAR_THRESHOLD - 1:
            await self.social_punishment(author.id, self.STAR_THRESHOLD * self.POINTS_PER_STAR, "unstarred")
        elif reaction.count >= self.STAR_THRESHOLD:
            await self.social_punishment(author.id, self.POINTS_PER_STAR, "remove star")


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(SocialCredit(bot))
