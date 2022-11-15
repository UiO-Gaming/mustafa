import re

import discord
from discord.ext import commands


class FunReplies(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def reply_to_triggers(self, message: discord.Message):
        if message.author.bot:
            return

        message_content = message.content.lower()

        if re.search(r'(^|\W)borgerlønn(\W|$)', message_content, flags=re.IGNORECASE):
            await message.channel.send('<@267415183931080715> DE SNAKKER OM BORGERLØNN')

        elif re.search(r'(^|\W)olof palme(\W|$)', message_content, flags=re.IGNORECASE):
            await message.channel.send('Jeg vet hvem som drepte Olof Palme 👀')

        elif re.search(r'(\W|\s)*le+s+go+(\s|\W)*', message_content):
            await message.channel.send('https://cdn.discordapp.com/attachments/750052141346979850/' +
                                       '824764933513281596/3xhpwbakz2361.png')

        elif re.search(r'^((er det|hvor)\s+)*(noen|folk|mange)\s+på\s+(rommet|neuf)\?*$', message_content, flags=re.IGNORECASE):
            await message.channel.send('Ja, <@554977854971183125> bor der')

        elif re.search(r'(^|\W)+ye+et($|\W)+', message_content, flags=re.IGNORECASE):
            await message.channel.send('<:Nei:826593267642662912>')


async def setup(bot):
    bot.add_listener(FunReplies(bot).reply_to_triggers, 'on_message')
    await bot.add_cog(FunReplies(bot))
