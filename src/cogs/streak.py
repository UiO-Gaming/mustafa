from datetime import datetime
from datetime import timezone

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks

from cogs.utils import discord_utils
from cogs.utils import embed_templates
from cogs.utils import misc_utils


class Streak(commands.Cog):
    """Cog for handling message streaks on the server"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot

        self.cursor = self.bot.db_connection.cursor()
        self.init_db()

        # Cache to avoid having to insert to the db for every message
        self.streak_cache = {}
        self.populate_cache()

        self.streak_check.start()
        self.insert_cache_loop.start()

    def init_db(self):
        """
        Create the necessary tables for the streak cog to work
        """

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS streak (
                discord_id BIGINT PRIMARY KEY,
                streak_start_id TEXT NOT NULL,
                streak_start_time timestamp NOT NULL,
                latest_post_time timestamp NOT NULL
            );
            """
        )

    async def cog_unload(self):
        self.bot.logger.info("Unloading cog")
        self.insert_cache_loop.cancel()
        self.streak_check.cancel()
        self.cursor.close()

    def populate_cache(self):
        """
        Populate the cache with the current streaks
        """

        self.cursor.execute(
            """
            SELECT *
            FROM streak;
            """
        )
        streaks = self.cursor.fetchall()

        for streak in streaks:
            self.streak_cache[streak[0]] = {
                "first_post_id": streak[1],
                "first_post_time": streak[2],
                "latest_post_time": streak[3],
            }

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Update the latest post time for a user

        Parameters
        ----------
        message (discord.Message): The message
        """

        if message.author.bot:
            return

        # Cache message stuff
        if message.author.id in self.streak_cache:
            self.streak_cache[message.author.id]["latest_post_time"] = message.created_at
        else:
            self.streak_cache[message.author.id] = {
                "first_post_id": f"{message.channel.id}-{message.id}",
                "first_post_time": message.created_at,
                "latest_post_time": message.created_at,
            }

    @tasks.loop(minutes=10)
    async def insert_cache_loop(self):
        """
        Inserts cache into the database every 10 minutes
        """

        await self.insert_cache()

    @insert_cache_loop.after_loop
    async def on_insert_cache_loop_cancel(self):
        self.bot.logger.info("Insert cache loop cancelled")
        if self.insert_cache_loop.is_being_cancelled() and self.streak_cache:
            await self.insert_cache()

    async def insert_cache(self):
        """
        Inserts cache into the database
        """

        self.bot.logger.info("Inserting cache into database")

        # Insert into database
        for user_id, user_data in self.streak_cache.items():
            self.cursor.execute(
                """
                INSERT INTO streak (discord_id, streak_start_id, streak_start_time, latest_post_time)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (discord_id) DO UPDATE
                SET latest_post_time = %s;
                """,
                (
                    user_id,
                    user_data["first_post_id"],
                    user_data["first_post_time"],
                    user_data["latest_post_time"],
                    user_data["latest_post_time"],
                ),
            )

    @tasks.loop(time=misc_utils.MIDNIGHT)
    async def streak_check(self):
        """
        Check if anyone has lost their streak
        """

        # Clear cache to make sure all streaks are up to date
        if self.streak_cache:
            await self.insert_cache()

        self.cursor.execute(
            """
            SELECT discord_id, latest_post_time
            FROM streak;
            """
        )
        streaks = self.cursor.fetchall()

        for streak in streaks:
            if (datetime.now(timezone.utc) - streak[2]).days > 1:
                self.cache.pop(streak[1])
                self.cursor.execute(
                    """
                    DELETE FROM streak
                    WHERE discord_id = %s;
                    """,
                    (streak[1],),
                )

    @streak_check.after_loop
    async def on_streak_check_cancel(self):
        self.bot.logger.info("Streak check loop cancelled")
        if self.streak_check.is_being_cancelled():
            await self.streak_check()

    streak_group = app_commands.Group(name="streak", description="Snapchat streaks, men for Discord")

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @streak_group.command(name="se", description="Se din eller en annen brukers streak")
    async def streak_user(self, interaction: discord.Interaction, bruker: discord.Member | discord.User | None = None):
        """
        Get the current streak for a user

        Parameters
        ----------
        interaction (discord.Interaction): The interaction
        bruker (discord.Member | discord.User | None): The user to get the streak for
        """

        await interaction.response.defer()

        if not bruker:
            bruker = interaction.user

        self.cursor.execute(
            """
            SELECT streak_start_id, streak_start_time
            FROM streak
            WHERE discord_id = %s;
            """,
            (bruker.id,),
        )
        streak = self.cursor.fetchone()

        if not streak:
            return await interaction.followup.send(embed=embed_templates.error_warning("Brukeren har ikke noen streak"))

        streak_msg_channel, streak_msg_id = streak[0].split("-")
        streak_msg_channel, streak_msg_id = int(streak_msg_channel), int(streak_msg_id)
        try:
            streak_msg_channel = await interaction.guild.fetch_channel(streak_msg_channel)
            streak_message = await streak_msg_channel.fetch_message(streak_msg_id)
        except (discord.NotFound, discord.Forbidden, AttributeError):
            streak_message = None

        if not streak_message:
            streak_msg_time = datetime.fromtimestamp(streak[2])
            streak_msg_link_txt = "*Meldingen kunne ikke lastes inn*"
            streak_msg_link = ""
        else:
            streak_msg_time = streak_message.created_at
            streak_msg_link_txt = "Meldingen"
            streak_msg_link = streak_message.jump_url

        streak_days = (datetime.now(timezone.utc) - streak_msg_time).days
        streak_msg_timestamp = discord.utils.format_dt(streak_msg_time, "F")

        embed = discord.Embed(title="Streak", description=bruker.mention)
        embed.set_author(name=bruker.name, icon_url=bruker.avatar)
        embed.add_field(name="Antall dager", value=streak_days)
        embed.add_field(
            name="Startet streaken", value=f"{streak_msg_timestamp}\n[{streak_msg_link_txt}]({streak_msg_link})"
        )
        await interaction.followup.send(embed=embed)

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @streak_group.command(name="topp", description="Se hvem som har høyest streak på serveren")
    async def streak_top(self, interaction: discord.Interaction):
        """
        Get the top streaks on the server

        Parameters
        ----------
        interaction (discord.Interaction): The interaction
        """

        await interaction.response.defer()

        self.cursor.execute(
            """
            SELECT discord_id, streak_start_time
            FROM streak
            ORDER BY streak_start_time;
            """
        )
        streaks = self.cursor.fetchall()

        if not streaks:
            return await interaction.followup.send(embed=embed_templates.error_warning("Ingen har noen streak enda"))

        streaks_formatted = [
            f"**#{s[0]+1}** <@{s[1][0]}> - {(datetime.now() - s[1][1]).days} dager" for s in enumerate(streaks)
        ]

        paginator = misc_utils.Paginator(streaks_formatted)
        view = discord_utils.Scroller(paginator, interaction.user)

        embed = view.construct_embed(discord.Embed(title="Toppliste for streaks"))
        await interaction.followup.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(Streak(bot))
