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

        # Cache to avoid having to insert to the db for every message
        self.streak_cache = {}

    async def cog_load(self):
        """
        Set up the database before the cog is used
        """

        await self.init_db()
        await self.populate_cache()
        self.streak_check.start()
        self.insert_cache_loop.start()

    async def init_db(self):
        """
        Create the necessary tables for the streak cog to work
        """

        await self.bot.db.execute("""
            CREATE TABLE IF NOT EXISTS streak (
                discord_id BIGINT PRIMARY KEY,
                streak_start_id TEXT NOT NULL,
                streak_start_time timestamptz NOT NULL,
                latest_post_time timestamptz NOT NULL
            );
            """)

        await self.bot.db.execute("""
            DO $$
            BEGIN
                IF (
                    SELECT data_type
                    FROM information_schema.columns
                    WHERE table_schema = current_schema() AND table_name = 'streak' AND column_name = 'latest_post_time'
                ) = 'timestamp without time zone' THEN
                    ALTER TABLE streak
                        ALTER COLUMN streak_start_time TYPE timestamptz
                            USING streak_start_time AT TIME ZONE 'Europe/Oslo',
                        ALTER COLUMN latest_post_time TYPE timestamptz
                            USING latest_post_time AT TIME ZONE 'Europe/Oslo';
                END IF;
            END $$;
            """)

    async def cog_unload(self):
        self.bot.logger.info("Unloading cog")
        self.insert_cache_loop.cancel()
        self.streak_check.cancel()
        await self.insert_cache()

    async def populate_cache(self):
        """
        Populate the cache with the current streaks
        """

        streaks = await self.bot.db.fetchall("""
            SELECT discord_id, streak_start_id, streak_start_time, latest_post_time
            FROM streak;
            """)

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

        self.record_message(message)

    def record_message(self, message: discord.Message):
        """
        Count a message towards its author's streak

        Parameters
        ----------
        message (discord.Message): The message
        """

        if streak := self.streak_cache.get(message.author.id):
            streak["latest_post_time"] = max(streak["latest_post_time"], message.created_at)
        else:
            self.streak_cache[message.author.id] = {
                "first_post_id": f"{message.channel.id}-{message.id}",
                "first_post_time": message.created_at,
                "latest_post_time": message.created_at,
            }

    @tasks.loop(minutes=10)
    @misc_utils.log_errors
    async def insert_cache_loop(self):
        """
        Inserts cache into the database every 10 minutes
        """

        await self.insert_cache()

    @insert_cache_loop.before_loop
    async def catch_up_on_missed_messages(self):
        """
        Count messages sent while the bot was offline, so streaks aren't lost because of downtime.
        A streak survives the midnight check if its latest post is less than a day old,
        so only messages since the last midnight can make a difference
        """

        await self.bot.wait_until_ready()

        since = discord.utils.utcnow().astimezone(self.bot.timezone).replace(hour=0, minute=0, second=0, microsecond=0)
        counted = 0
        for guild in self.bot.guilds:
            channels = [c for c in guild.channels if isinstance(c, discord.abc.Messageable)] + list(guild.threads)
            for channel in channels:
                if not channel.permissions_for(guild.me).read_message_history:
                    continue

                try:
                    async for message in channel.history(limit=None, after=since):
                        if not message.author.bot:
                            self.record_message(message)
                            counted += 1
                except discord.HTTPException as e:
                    self.bot.logger.warning(
                        f"Could not read the history of {channel} while catching up on streaks: {e}"
                    )

        self.bot.logger.info(f"Counted {counted} messages since {since} towards streaks")

    async def insert_cache(self):
        """
        Inserts cache into the database
        """

        self.bot.logger.info("Inserting cache into database")

        # Snapshot the cache before awaiting, since new messages can change it while we wait for the database
        rows = [
            (
                user_id,
                user_data["first_post_id"],
                user_data["first_post_time"],
                user_data["latest_post_time"],
                user_data["latest_post_time"],
            )
            for user_id, user_data in self.streak_cache.items()
        ]
        if not rows:
            return

        await self.bot.db.executemany(
            """
            INSERT INTO streak (discord_id, streak_start_id, streak_start_time, latest_post_time)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (discord_id) DO UPDATE
            SET latest_post_time = %s;
            """,
            rows,
        )

    @tasks.loop(time=misc_utils.MIDNIGHT)
    @misc_utils.log_errors
    async def streak_check(self):
        """
        Check if anyone has lost their streak
        """

        self.bot.logger.info("Checking streaks")

        # Clear cache to make sure all streaks are up to date
        if self.streak_cache:
            await self.insert_cache()

        streaks = await self.bot.db.fetchall("""
            SELECT discord_id, latest_post_time
            FROM streak;
            """)

        for streak in streaks:
            if (discord.utils.utcnow() - streak[1]).days >= 1:
                self.bot.logger.info(f"User {streak[0]} lost their streak")
                self.streak_cache.pop(streak[0])
                await self.bot.db.execute(
                    """
                    DELETE FROM streak
                    WHERE discord_id = %s;
                    """,
                    (streak[0],),
                )

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

        streak = await self.bot.db.fetchone(
            """
            SELECT streak_start_id, streak_start_time
            FROM streak
            WHERE discord_id = %s;
            """,
            (bruker.id,),
        )

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
            streak_msg_time = streak[1]
            streak_msg_link = "*Meldingen kunne ikke lastes inn*"
        else:
            streak_msg_time = streak_message.created_at
            streak_msg_link = f"[Meldingen]({streak_message.jump_url})"

        streak_days = (discord.utils.utcnow() - streak_msg_time).days
        streak_msg_timestamp = discord.utils.format_dt(streak_msg_time, "F")

        embed = discord.Embed(title="Streak", description=bruker.mention)
        embed.set_author(name=bruker.name, icon_url=bruker.avatar)
        embed.add_field(name="Antall dager", value=streak_days)
        embed.add_field(name="Startet streaken", value=f"{streak_msg_timestamp}\n{streak_msg_link}")
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

        streaks = await self.bot.db.fetchall("""
            SELECT discord_id, streak_start_time
            FROM streak
            ORDER BY streak_start_time;
            """)

        if not streaks:
            return await interaction.followup.send(embed=embed_templates.error_warning("Ingen har noen streak enda"))

        streaks_formatted = [
            f"**#{s[0]+1}** <@{s[1][0]}> - {(discord.utils.utcnow() - s[1][1]).days} dager" for s in enumerate(streaks)
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
