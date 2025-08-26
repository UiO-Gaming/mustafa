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

------ TO-DO ------
- score sitte i afk
+ score for å sitte i voice per time
"""


@dataclass
class CreditUser:
    user_id: int
    credit_score: int


class SocialCredit(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.fuck_uwu.start()

        self.START_POINTS = 1000
        self.cursor = self.bot.db_connection.cursor()
        self.init_db()

    def init_db(self):
        """
        Create the necessary tables for the social credit cog to work
        """

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS social_credit (
                user_id BIGINT PRIMARY KEY,
                credit_score SMALLINT NOT NULL
            );
            """
        )

    def add_new_citizen(func):
        """
        Decorator that, when used, make sure that a user is inserted
        into the database before executing the function
        """

        async def wrapper(*args, **kwargs):
            self = args[0]
            self.cursor.execute("SELECT user_id FROM social_credit WHERE user_id = %s", (args[1],))
            if not self.cursor.fetchone():
                self.add_citizen(args[1])
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

    def add_citizen(self, user_id: int):
        """
        Adds a user to the database

        Parameters
        ----------
        user_id (int): The user's Discord ID
        """

        self.cursor.execute(
            """
            INSERT INTO social_credit
            (user_id, credit_score)
            VALUES (%s, %s)
            """,
            (user_id, self.START_POINTS),
        )

    @tasks.loop(time=misc_utils.MIDNIGHT, reconnect=True)
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
        if not (weeb_role := guild.get_role(803629993539403826)):
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

    async def cog_unload(self):
        self.bot.logger.info("Unloading cog")
        self.fuck_uwu.cancel()
        self.cursor.close()

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
        self.cursor.execute(
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
        self.cursor.execute(
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
    async def credits(self, interaction: discord.Interaction, *, bruker: discord.Member | None = None):
        """
        Check the social credit score of a given user

        Parameters
        ----------
        interaction (discord.Interaction): The interaction object
        bruker (discord.Member | None): The user to check the score of. Defaults to the user who invoked the command
        """

        if not bruker:
            bruker = interaction.user

        self.cursor.execute(
            """
            SELECT * FROM social_credit
            WHERE user_id = %s
            """,
            (bruker.id,),
        )
        result = self.cursor.fetchone()

        if not result:
            return await interaction.response.send_message(
                embed=embed_templates.error_warning(f"{bruker.mention} er ikke registrert i databasen")
            )

        db_user = CreditUser(*result)

        embed = discord.Embed(description=(f"{bruker.mention} har `{db_user.credit_score}` social credits"))
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

        self.cursor.execute(
            """
            SELECT * FROM social_credit
            ORDER BY credit_score DESC
            """
        )
        result = self.cursor.fetchall()

        if not result:
            return await interaction.send(
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

        if message.channel.id == 754706204349038644:
            await self.social_punishment(message.author.id, 25, "politics")

    @roll(percent=25)
    async def chad_message(self, message: discord.Message):
        """
        Rewards users for writing in the member-chat channel

        Parameters
        ----------
        message (discord.Message): The message object
        """

        if message.channel.id == 811606213665357824:
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

        if message.created_at.hour in illegal_hours:
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

        if message.created_at.hour in happy_hours:
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
        if message.channel.id == 865970753748074576 and message.mentions:
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

        if reaction.emoji == "⭐":
            if reaction.message.author == user:
                await self.social_punishment(user.id, 100, "self-star")
            elif reaction.count == 3:
                await self.social_punishment(
                    user.id, (len(reaction.message.reactions) - 1) * 25, "remove already accumulated stars"
                )
                await self.social_reward(user.id, 25 * len(reaction.message.reactions), "add new stars")

    @commands.Cog.listener("on_reaction_remove")
    async def on_star_remove(self, reaction: discord.Reaction, user: discord.User | discord.Member):
        """
        Deducts points who have a star reaction removed from their message
        """

        if user.bot:
            return

        if reaction.emoji == "⭐" and reaction.count >= 3:
            await self.social_punishment(user.id, 25, "remove star")


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(SocialCredit(bot))
