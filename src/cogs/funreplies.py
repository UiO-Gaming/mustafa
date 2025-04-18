import re
from datetime import datetime

import discord
from discord.ext import commands


class FunReplies(commands.Cog):
    """Reply to messages that trigger certain key words/phrases"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance. In this case not used
        """

        # Cooldowns for trigger words
        #
        # This is kind of a shitty way to do it but I'm too lazy to implement anything good right now
        self.cooldown_seconds = 600
        initial_datetime = datetime(
            2000, 9, 11
        )  # Set initial datetime far in the past to allow triggering right after boot
        self.previous_invokations = {
            "olof palme": initial_datetime,
            "yeet": initial_datetime,
            "drikke": initial_datetime,
            "sivert": initial_datetime,
            "borgerlønn": initial_datetime,
            "bærum": initial_datetime,
        }

    @commands.Cog.listener("on_message")
    async def reply_to_triggers(self, message: discord.Message):
        """
        Replies to messages that trigger certain key words/phrases

        Parameters
        ----------
        message (discord.Message): Message object to check for triggers to
        """

        if message.author.bot:
            return

        # TODO: add ability to disable single triggers?
        # Auto assign cooldown_key?
        triggers = [
            (r"(^|\W)borgerlønn(\W|$)", "@ sivert DE SNAKKER OM BORGERLØNN", "borgerlønn"),
            (r"(^|\W)olof palme(\W|$)", "Jeg vet hvem som drepte Olof Palme 👀", "olof palme"),
            (r"(^|\W)+ye+et($|\W)+", "<:Nei:826593267642662912>", "yeet"),
            (
                r"(^|\W)skal? aldri drikke?[\w\s]*igjen($|\W)+",
                ":billed_cap:\nhttps://cdn.discordapp.com/attachments/811606213665357824/1320756460321378396/v15044gf0000ctk1refog65kh5pqtpkg.mov",
                "drikke",
            ),
            (r"(^|\W)(jeg?|(e|æ)(g|j)?|i) er? sivert arntzen($|\W)+", "Nei, jeg er Sivert Arntzen!", "sivert"),
            (r"(^|\W)bærum(\W|$)", "Sa noen Bærum? 👀🍾 <@205741213050077185>", "bærum"),
        ]

        for trigger in triggers:
            regex, reply, cooldown_key = trigger
            if await self.trigger(
                message=message, regex_match=regex, reply=reply, cooldown_key=cooldown_key, regex_flags=re.IGNORECASE
            ):
                return

    async def trigger(
        self, message: discord.Message, regex_match: str, reply: str, cooldown_key: str, regex_flags=None
    ) -> bool:
        """
        Add a trigger to the bot

        Parameters
        ----------
        message (discord.Message): The message object to check for triggers
        regex_match (str): The regex pattern to match
        reply (str): The reply to send
        cooldown_key (str): The key to use for cooldown tracking
        regex_flags (int): The regex flags to use

        Returns
        ----------
        bool: Whether or not the reply was triggered
        """

        if (datetime.now() - self.previous_invokations[cooldown_key]).seconds < self.cooldown_seconds:
            return False

        if re.search(regex_match, message.content, flags=regex_flags):
            await message.reply(reply)
            self.previous_invokations[cooldown_key] = datetime.now()
            return True

        return False


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(FunReplies(bot))
