import discord
import requests
from discord import app_commands
from discord.ext import commands
from mcrcon import MCRcon

from cogs.utils import embed_templates


class MCWhitelist(commands.Cog):
    """Standalone cog for handling whitelisting of Discord users on the Minecraft server"""

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
        """
        Create the necessary tables for the mc_whitelist cog to work
        """

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS mc_whitelist (
                discord_id BIGINT PRIMARY KEY,
                minecraft_id TEXT NOT NULL
            );
            """
        )

    whitelist_group = app_commands.Group(
        name="whitelist", description="Registrer eller fjern deg selv fra vår Minecraft whitelist"
    )

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 5)
    @whitelist_group.command(name="registrer", description="Whitelist minecraftbrukeren din på serveren vår")
    async def whitelist_add(self, interaction: discord.Interaction, minecraftbrukernavn: str):
        """
        Whitelist a minecraft user on the Minecraft server

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        minecraftbrukernavn (str): Minecraft username
        """

        # Fetch minecraft uuid from api
        data = requests.get(f"https://api.mojang.com/users/profiles/minecraft/{minecraftbrukernavn}", timeout=10)
        if data.status_code != 200:
            return await interaction.response.send_message(
                embed=embed_templates.error_warning(f"Brukeren `{minecraftbrukernavn}` finnes ikke på minecraft"),
                ephemeral=True,
            )

        data = data.json()

        # Check if the discord user or minecraft user is in the db
        self.cursor.execute(
            """
            SELECT *
            FROM mc_whitelist
            WHERE minecraft_id = %s OR discord_id = %s
            """,
            (data["id"], interaction.user.id),
        )
        if self.cursor.fetchone():
            return await interaction.response.send_message(
                embed=embed_templates.error_warning(
                    "Du har allerede whitelisted en bruker eller så er brukeren du oppga whitelisted"
                )
            )

        # Whitelist user on minecraft server
        # Unfortunately, this requires an active connection to the server, with correct credentials
        # Also unfortunate, we seemingly need to wrap the context manager like this to catch any exceptions
        try:
            with MCRcon(host="127.0.0.1", password=self.bot.mc_rcon_password, port=25575) as mcr:
                mcr.command(f'whitelist add {data["id"]}')
                mcr.command("whitelist reload")
        except Exception as e:
            self.bot.logger.error(f"Failed to use RCON: {e}")
            return await interaction.response.send_message(
                embed=embed_templates.error_fatal(
                    "Klarte ikke å koble til minecraftserveren. Ta kontakt med din lokale teknisk ansvarlige",
                )
            )

        # Add user to db
        self.cursor.execute(
            """
            INSERT INTO mc_whitelist (discord_id, minecraft_id)
            VALUES (%s, %s)
            """,
            (interaction.user.id, data["id"]),
        )

        self.bot.logger.info(f"Whitelisted {data['name']} for {interaction.user.name}")

        await interaction.response.send_message(
            embed=embed_templates.success(f'`{data["name"]}` er nå tilknyttet din discordbruker og whitelisted!')
        )

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 5)
    @whitelist_group.command(name="fjern", description="Fjern deg selv fra whitelist på minecraftserveren vår")
    async def whitelist_remove(self, interaction: discord.Interaction):
        """
        Remove the invoking user from the minecraft server whitelist

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        # Check if the discord user is in the db
        self.cursor.execute(
            """
            SELECT *
            FROM mc_whitelist
            WHERE discord_id = %s
            """,
            (interaction.user.id,),
        )
        if not (result := self.cursor.fetchone()):
            return await interaction.response.send_message(
                embed=embed_templates.error_warning("Du har ikke en whitelisted bruker på vår minecraftserver")
            )
        mc_id = result[1]

        # Remove user from whitelist on minecraft server
        # Unfortunately, this requires an active connection to the server, with correct credentials
        # Also unfortunate, we seemingly need to wrap the context manager like this to catch any exceptions
        try:
            with MCRcon(host="127.0.0.1", password=self.bot.mc_rcon_password, port=25575) as mcr:
                mcr.command(f"whitelist remove {mc_id}")
                mcr.command("whitelist reload")
        except Exception as e:
            self.bot.logger.error(f"Failed to use RCON: {e}")
            return await interaction.response.send_message(
                embed=embed_templates.error_fatal(
                    "Klarte ikke å koble til minecraftserveren. Ta kontakt med din lokale teknisk ansvarlige",
                )
            )

        # Remove user from db
        self.cursor.execute(
            """
            DELETE FROM mc_whitelist
            WHERE discord_id = %s
            """,
            (interaction.user.id,),
        )

        self.bot.logger.info(f"Removed {mc_id} (discord: {interaction.user.name}) from whitelist")

        await interaction.response.send_message(embed=embed_templates.success("Du er nå fjernet fra whitelist!"))


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(MCWhitelist(bot))
