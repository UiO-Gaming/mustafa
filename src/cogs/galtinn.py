from datetime import datetime

import discord
import requests
from discord import app_commands
from discord.ext import commands

from cogs.utils import embed_templates


class Galtinn(commands.Cog):
    """Galtinn - Membership database for the Norwegian Student Society"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot

    galtinn_group = app_commands.Group(
        name="galtinn", description="Kommandoer for Galtinn - Medlemsdatabasen til Det Norske Studentersamfund"
    )

    @app_commands.checks.cooldown(1, 5)
    @galtinn_group.command(name="medlemskap", description="Sjekk medlemskap i Det Norske Studentersamfund")
    async def medlemskap(
        self, interaction: discord.Interaction, brukernavn: str | None = None, discordbruker: discord.User | None = None
    ):
        """
        Check someone's membership status in the norwegian student society

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        if discordbruker and brukernavn:
            embed = embed_templates.error_fatal("Du kan ikke oppgi både brukernavn og discordbruker")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if not brukernavn and not discordbruker:
            discordbruker = interaction.user

        # Check if the user has registered their Discord account in Galtinn.
        # We do this because we don't want just anyone fetching data
        # from the database. We only want the users who have registered
        data = requests.get(
            f"{self.bot.galtinn['api_url']}/users/?discord_profile__discord_id={interaction.user.id}&format=json",
            headers={"Authorization": f"Token {self.bot.galtinn['auth_token']}"},
        )
        if data.status_code != 200 or not data.json():
            self.logger.error(f"Failed to fetch data from Galtinn API: {data.status_code} - {data.text}")
            embed = embed_templates.error_fatal("Noe gikk galt under henting av data fra Galtinn")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        data = data.json()

        if not data["results"]:
            embed = embed_templates.error_warning("""
                Du har ikke registrert din Discord-konto i Galtinn. Vi lar bare folk med brukere i Galtinn se data.

                For å koble brukerene dine sammen, besøk [DNS sin Discord](https://discord.gg/SE2ChXjVeV) og skriv:
                `/galtinn registrer`
                """)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Only make new request if given user is different from command invoker
        # This is done in order to avoid redundant requests
        if (discordbruker and discordbruker.id != data["results"][0]["discord_profile"]["discord_id"]) or brukernavn:
            params = {
                "discord_profile__discord_id": discordbruker.id if discordbruker else None,
                "username": brukernavn,
                "format": "json",
            }
            data = requests.get(
                f"{self.bot.galtinn['api_url']}/users/",
                params=params,
                headers={"Authorization": f"Token {self.bot.galtinn['auth_token']}"},
            )
            if data.status_code != 200 or not data.json():
                self.logger.error(f"Failed to make second Galtinn API request: {data.status_code} - {data.text}")
                embed = embed_templates.error_fatal("Noe gikk galt under henting av data fra Galtinn")
                return await interaction.response.send_message(embed=embed, ephemeral=True)

            data = data.json()

            if not data["results"]:
                if discordbruker:
                    embed = embed_templates.error_warning(
                        "Brukeren du forespurte har ikke koblet Discordbrukeren sin til Galtinn"
                    )
                else:
                    embed = embed_templates.error_warning("Brukeren du forespurte finnes ikke")
                return await interaction.response.send_message(embed=embed, ephemeral=True)

        user = data["results"][0]
        username = user["username"]
        last_membership = user["last_membership"]

        if not last_membership:
            membership_status = "Har aldri vært medlem"
        else:
            membership_status = "Ja" if last_membership["is_valid"] else "Nei"
            if last_membership["membership_type"] != "lifelong":
                expiration_date = datetime.strptime(last_membership["end_date"], "%Y-%m-%d")
                expires = discord.utils.format_dt(expiration_date, "D")
                time_left = discord.utils.format_dt(expiration_date, "R")

        embed = discord.Embed()
        embed.set_author(name=username)
        embed.color = discord.Color.green() if last_membership["is_valid"] else discord.Color.red()
        if user["discord_profile"]:
            embed.description = f"<@{user['discord_profile']['discord_id']}>"
        embed.add_field(name="Medlem?", value=membership_status)
        if last_membership:
            embed.add_field(name="Medlemskapstype", value=last_membership["membership_type"])
            if last_membership["membership_type"] != "lifelong":
                embed.add_field(name="Gyldig til", value=f"{expires}\n{time_left}")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(Galtinn(bot))
