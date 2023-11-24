import discord
from discord import app_commands
from discord.ext import commands

from cogs.utils import discord_utils
from cogs.utils import embed_templates


class Gullkorn(commands.Cog):
    """Stand alone cog for handling whitelisting of Discord users on the Minecraft server"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot
        self.cursor = self.bot.db_connection.cursor()
        self.init_db()

    def init_db(self):
        """Create the necessary tables for the gullkorn cog to work."""

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS gullkorn (
                discord_id BIGINT PRIMARY KEY,
                times_cited INT NOT NULL DEFAULT 0,
                citations_posted INT NOT NULL DEFAULT 0
            );
            """
        )
        self.cursor.execute(
            """
            CREATE OR REPLACE VIEW most_cited AS
            SELECT discord_id, times_cited
            FROM gullkorn
            ORDER BY times_cited DESC;
            """
        )
        self.cursor.execute(
            """
            CREATE OR REPLACE VIEW most_frequent_posters AS
            SELECT discord_id, citations_posted
            FROM gullkorn
            ORDER BY citations_posted DESC;
            """
        )

    def __construct_data_string(self, data: list[tuple[int, int, int]]) -> str:
        """
        Constructs a formatted string displaying lists of gullkorn data

        Parameters
        ----------
        data (list[tuple[int, int, int]]): List of database rows

        Returns
        ----------
        str: The input data formatted into a prettified string
        """

        formatted_string = ""
        for i, row in enumerate(data):
            user = self.bot.get_user(row[0])
            if user:
                formatted_string += f"**#{i+1}** {user.name} - *{row[1]}*\n"
            else:
                formatted_string += f"**#{i+1}** `Ukjent bruker` - *{row[1]}*\n"

        return formatted_string

    async def gullkorn_listener(self, message: discord.Message):
        """
        Listens for messages in the gullkorn channel and updates the database accordingly

        Parameters
        ----------
        message (discord.Message): Message object to check for triggers to
        """

        if message.author.bot or message.channel.id != 865970753748074576 or not message.mentions:
            return

        for user in message.mentions:
            self.cursor.execute(
                """
                INSERT INTO gullkorn (discord_id, times_cited, citations_posted)
                VALUES (%s, 1, 0)
                ON CONFLICT (discord_id)
                DO UPDATE SET times_cited = gullkorn.times_cited + 1;
                """,
                (user.id,),
            )

        self.cursor.execute(
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
    async def gullkorn_stats(self, interaction: discord.Interaction, bruker: discord.Member | None = None):
        """
        Fetches gullkorn stats for a user or the whole server

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        bruker (discord.Member, optional): Discord user to fetch stats for. Defaults to None.
        """

        if bruker:
            result = self.cursor.execute(
                """
                SELECT *
                FROM gullkorn
                WHERE discord_id = %s;
                """,
                (bruker.id,),
            )

            result = self.cursor.fetchone()

            if not result:
                return await interaction.response.send_message(
                    embed=embed_templates.error_fatal(interaction, text="Ingen data om denne brukeren funnet"),
                    ephemeral=False,
                )

            embed = discord.Embed(
                title=f"Gullkornstatistikk for `{bruker.name}`",
                color=discord_utils.get_color(bruker),
            )
            embed.set_thumbnail(url=bruker.avatar)
            embed.add_field(name="Antall gullkorn", value=result[1])
            embed.add_field(name="Antall gullkorn postet", value=result[2])
            return await interaction.response.send_message(embed=embed, ephemeral=False)

        summary = self.cursor.execute(
            """
            SELECT SUM(citations_posted)
            FROM gullkorn;
            """
        )
        summary = self.cursor.fetchone()

        most_cited = self.cursor.execute(
            """
            SELECT *
            FROM most_cited
            LIMIT 5;
            """
        )
        most_cited = self.cursor.fetchall()

        citations_posted = self.cursor.execute(
            """
            SELECT *
            FROM most_frequent_posters
            LIMIT 5;
            """
        )
        citations_posted = self.cursor.fetchall()

        most_cited_string = self.__construct_data_string(most_cited)
        citations_posted_string = self.__construct_data_string(citations_posted)

        gullkorn_first_msg = "https://canary.discord.com/channels/747542543750660178/865970753748074576/1034587913285025912"  # noqa: E501

        embed = discord.Embed(title="Gullkornstatistikk for serveren")
        embed.description = f"Antall gullkorn siden [denne meldingen]({gullkorn_first_msg}): *{summary[0]}*"
        embed.add_field(name="Mest sitert", value=most_cited_string, inline=False)
        embed.add_field(name="Postet mest", value=citations_posted_string, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=False)


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    bot.add_listener(Gullkorn(bot).gullkorn_listener, "on_message")
    await bot.add_cog(Gullkorn(bot))
