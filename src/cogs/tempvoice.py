import discord
from discord import app_commands
from discord.ext import commands

from cogs.utils import embed_templates
from cogs.utils.discord_utils import TempVoiceHelper


class TempVoice(commands.Cog):
    """Allows users to create a temporary channel that will be deleted after 5 minutes of inactivity"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.temp_voice_helper = TempVoiceHelper(bot)

    async def cog_load(self):
        await self.temp_voice_helper.start()

    async def cog_unload(self):
        self.temp_voice_helper.check_temp_vc_channels.cancel()

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        """
        Listen for disconnects from the temporary voice channels
        """

        await self.temp_voice_helper.on_voice_state_update(member, before, after)

    @app_commands.checks.bot_has_permissions(manage_channels=True, embed_links=True)
    @app_commands.checks.cooldown(1, 300)
    @app_commands.command(name="tempvoice")
    @app_commands.rename(name="navn", limit="grense")
    @app_commands.describe(name="Navnet på kanalen", limit="Maks antall brukere. 0 betyr ingen grense")
    async def tempvoice(
        self,
        interaction: discord.Interaction,
        name: app_commands.Range[str, 1, 100],
        limit: app_commands.Range[int, 0, 99] = 0,
    ):
        """
        Create a temporary voice channel

        Parameters
        ----------
        interaction (discord.Interaction): The interaction object
        name (str): The name of the channel
        limit (int): The user limit of the channel. 0 means no limit
        """

        channel = await self.temp_voice_helper.create_temp_voice(interaction, name, limit)
        if not channel:
            return

        await interaction.response.send_message(
            embed=embed_templates.success(
                f"{channel.mention} ble opprettet. Den vil bli slettet etter cirka 1 minutt uten aktivitet.",
            )
        )


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(TempVoice(bot))
