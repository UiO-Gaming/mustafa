import discord
from discord import app_commands
from discord.ext import commands

from cogs.utils import embed_templates


class Gullkorn(commands.Cog):
    """Tracks stats for gullkorn"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot

    async def cog_load(self):
        """
        Set up the database before the cog is used
        """

        await self.init_db()

    async def init_db(self):
        """
        Create the necessary tables for the gullkorn cog to work
        """

        await self.bot.db.execute("""
            CREATE TABLE IF NOT EXISTS gullkorn (
                discord_id BIGINT PRIMARY KEY,
                times_cited INT NOT NULL DEFAULT 0,
                citations_posted INT NOT NULL DEFAULT 0
            );
            """)
        await self.bot.db.execute("""
            CREATE OR REPLACE VIEW most_cited AS
            SELECT discord_id, times_cited
            FROM gullkorn
            ORDER BY times_cited DESC;
            """)
        await self.bot.db.execute("""
            CREATE OR REPLACE VIEW most_frequent_posters AS
            SELECT discord_id, citations_posted
            FROM gullkorn
            ORDER BY citations_posted DESC;
            """)

    def construct_data_string(self, data: list[tuple[int, int, int]]) -> str:
        """
        Constructs a formatted string displaying lists of gullkorn data

        Parameters
        ----------
        data (list[tuple[int, int, int]]): List of database rows

        Returns
        ----------
        (str): The input data formatted into a prettified string
        """

        formatted_string = ""
        for i, row in enumerate(data):
            user = self.bot.get_user(row[0])
            if user:
                formatted_string += f"**#{i+1}** {user.name} - *{row[1]}*\n"
            else:
                formatted_string += f"**#{i+1}** `Ukjent bruker` - *{row[1]}*\n"

        return formatted_string

    @commands.Cog.listener("on_message")
    async def gullkorn_listener(self, message: discord.Message):
        """
        Listens for messages in the gullkorn channel and updates the database accordingly

        Parameters
        ----------
        message (discord.Message): The message that was sent
        """

        if message.author.bot or message.channel.id != self.bot.channel_ids.get("gullkorn") or not message.mentions:
            return

        for user in message.mentions:
            await self.bot.db.execute(
                """
                INSERT INTO gullkorn (discord_id, times_cited, citations_posted)
                VALUES (%s, 1, 0)
                ON CONFLICT (discord_id)
                DO UPDATE SET times_cited = gullkorn.times_cited + 1;
                """,
                (user.id,),
            )

        await self.bot.db.execute(
            """
            INSERT INTO gullkorn (discord_id, times_cited, citations_posted)
            VALUES (%s, 0, 1)
            ON CONFLICT (discord_id)
            DO UPDATE SET citations_posted = gullkorn.citations_posted + 1;
            """,
            (message.author.id,),
        )

    gullkorn_group = app_commands.Group(name="gullkorn", description="Se statistikk for gullkorn")

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 5)
    @gullkorn_group.command(
        name="statistikk", description="Se informasjon om gullkorn for en bruker eller hele serveren"
    )
    @app_commands.rename(user="bruker")
    @app_commands.describe(user="Brukeren du vil se statistikk for. Standard er deg selv")
    async def gullkorn_stats(self, interaction: discord.Interaction, user: discord.Member | None = None):
        """
        Fetches gullkorn stats for a user or the whole server

        Parameters
        ----------
        interaction (discord.Interaction): The slash command interaction
        user (discord.Member | None): The user to fetch stats for. Defaults to the invoking user
        """

        # This looks kinda ugly, ngl
        if user:
            result = await self.bot.db.fetchone(
                """
                SELECT *
                FROM gullkorn
                WHERE discord_id = %s;
                """,
                (user.id,),
            )

            if not result:
                return await interaction.response.send_message(
                    embed=embed_templates.error_warning("Ingen data om denne brukeren funnet"),
                    ephemeral=False,
                )

            embed = discord.Embed(
                title=f"Gullkornstatistikk for `{user.name}`",
                color=user.color,
            )
            embed.set_thumbnail(url=user.avatar)
            embed.add_field(name="Antall gullkorn", value=result[1])
            embed.add_field(name="Antall gullkorn postet", value=result[2])
            return await interaction.response.send_message(embed=embed, ephemeral=False)

        summary = await self.bot.db.fetchone("""
            SELECT SUM(citations_posted)
            FROM gullkorn;
            """)

        most_cited = await self.bot.db.fetchall("""
            SELECT *
            FROM most_cited
            LIMIT 5;
            """)

        citations_posted = await self.bot.db.fetchall("""
            SELECT *
            FROM most_frequent_posters
            LIMIT 5;
            """)

        most_cited_string = self.construct_data_string(most_cited)
        citations_posted_string = self.construct_data_string(citations_posted)

        GULLKORN_FIRST_MSG = "https://canary.discord.com/channels/747542543750660178/865970753748074576/1034587913285025912"  # noqa: E501

        embed = discord.Embed(title="Gullkornstatistikk for serveren")
        embed.description = f"Antall gullkorn siden [denne meldingen]({GULLKORN_FIRST_MSG}): *{summary[0]}*"
        embed.add_field(name="Mest sitert", value=most_cited_string, inline=False)
        embed.add_field(name="Postet mest", value=citations_posted_string, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=False)


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): The bot instance
    """

    await bot.add_cog(Gullkorn(bot))
