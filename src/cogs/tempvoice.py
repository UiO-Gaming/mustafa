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

        self.bot = bot
        self.temp_voice_helper = TempVoiceHelper(bot)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        """
        Listen for disconnects from the temporary voice channels
        """

        await self.temp_voice_helper.on_voice_state_update(member, before, after)

    @app_commands.checks.cooldown(1, 300)
    @app_commands.command(name="tempvoice")
    async def tempvoice(self, interaction: discord.Interaction, name: str, limit: int = 0):
        """
        Create a temporary voice channel

        Parameters
        ----------
        interaction (discord.Interaction): The interaction object
        name (str): The name of the channel
        limit (int): The user limit of the channel
        """

        channel = await self.temp_voice_helper.create_temp_voice(interaction, name, limit)

        await interaction.response.send_message(
            embed=embed_templates.success(
                interaction,
                text=f"{channel.mention} ble opprettet. Den vil bli slettet etter cirka 5 minutter uten aktivitet.",
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
