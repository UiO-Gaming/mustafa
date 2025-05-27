import random
from datetime import datetime

from discord.ext import commands
from discord.ext import tasks

from cogs.utils import misc_utils


class RepeatedMessages(commands.Cog):
    """Send messages at specific points of time"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.general_channel = 747542544291987597

        self.fredag.start()
        self.mandag.start()
        self.new_year.start()

    def cog_unload(self):
        self.fredag.cancel()
        self.mandag.cancel()
        self.new_year.cancel()

    @tasks.loop(time=misc_utils.MIDNIGHT)
    async def fredag(self):
        """
        Sends a message on Friday at 00:00
        """

        if datetime.now().weekday() != 4:
            return

        guild = self.bot.get_guild(self.bot.UIO_GAMING_GUILD_ID)
        channel = guild.get_channel(self.general_channel)

        videos = [
            "https://cdn.discordapp.com/attachments/750052141346979850/851216786259181578/video0.mp4",
            "https://cdn.discordapp.com/attachments/878368386671849582/1043133798512070666/durk_durk_fredag.mp4",
            "https://cdn.discordapp.com/attachments/878368386671849582/1043133820079177808/finfredag.png",
            "https://cdn.discordapp.com/attachments/878368386671849582/1043133832360120340/fredag_1.mp4",
            "https://cdn.discordapp.com/attachments/878368386671849582/1043133914316816424/shutup_friday.mp4",
            "https://cdn.discordapp.com/attachments/878368386671849582/1043133934915031040/uboot_fredag.mp4",
            "https://cdn.discordapp.com/attachments/747542544291987597/1037864063901909043/fredag_whole_store4.mp4",
            "https://cdn.discordapp.com/attachments/747542544291987597/1037864293154168863/fredag_wholesome.mp4",
            "https://cdn.discordapp.com/attachments/747542544291987597/1055835511366877244/received_914083109578582.gif",
            "https://cdn.discordapp.com/attachments/747542544291987597/1037866542328713256/fredag_i_norge.mp4",
            "https://cdn.discordapp.com/attachments/674726496878723082/1351613444125626460/skolebollefredag.mp4?ex=67db039c&is=67d9b21c&hm=cd1fa3fbd5e4e647f8528004a622f70f277e567b6ba9f7b192b5e6c1bc8da1d4&",  # noqa: E501
            "https://cdn.discordapp.com/attachments/674726496878723082/1377047504851570728/kriss_friyay.mp4?ex=68378aed&is=6836396d&hm=590daef172c17811cf0f59a94191b397d140a82b8e031da1bb7e6cb0a6796955&",  # noqa: E501
        ]

        video = random.choice(videos)

        await channel.send("NU ÄR DET FREDAG!\n" + video)

    @tasks.loop(time=misc_utils.MIDNIGHT)
    async def mandag(self):
        """
        Sends a message on Monday at 00:00
        """
        if datetime.now().weekday() != 0:
            return
        guild = self.bot.get_guild(self.bot.UIO_GAMING_GUILD_ID)
        channel = guild.get_channel(self.general_channel)
        await channel.send(
            "ENDELIG MANDAG!\n\n"
            # + "https://cdn.discordapp.com/attachments/678396498089738250/1168644637687283762/Snapchat-1787493720.mp4"  # noqa: E501
            + "https://cdn.discordapp.com/attachments/678396498089738250/862853827278929940/hvorfor_de_rike_br_spises.mp4"  # noqa: E501
        )

    @tasks.loop(time=misc_utils.MIDNIGHT)
    async def new_year(self):
        """
        Sends a message on New Year's Day at 00:00
        """

        if datetime.now().month != 1 or datetime.now().day != 1:
            return

        guild = self.bot.get_guild(self.bot.UIO_GAMING_GUILD_ID)
        channel = guild.get_channel(self.general_channel)
        await channel.send("GODT NYTTÅR!\n\nNå, meld dere inn i UiO Gaming igjen <:ThisIsAThreat:874998234072903710>")


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(RepeatedMessages(bot))
