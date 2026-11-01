import discord
from discord.ext import commands


class Fun(commands.Cog):
    """Simple commands that return short strings for the memes"""

    @commands.cooldown(1, 2, commands.BucketType.guild)
    @commands.command(name="norskeuniversiteter")
    async def norskeuniversiteter(self, ctx: commands.Context):
        """
        Sends a link to university meme image album

        Parameters
        ----------
        ctx (commands.Context): The command context
        """

        await ctx.reply("<https://imgur.com/a/uGopaSq>")

    @commands.cooldown(1, 2, commands.BucketType.guild)
    @commands.command(name="ifi")
    async def ifi(self, ctx: commands.Context):
        """
        ifi meme 1

        Parameters
        ----------
        ctx (commands.Context): The command context
        """

        await ctx.reply("https://i.imgur.com/ypyK1mi.jpg")

    @commands.cooldown(1, 2, commands.BucketType.guild)
    @commands.command(name="ifi2")
    async def ifi2(self, ctx: commands.Context):
        """
        ifi meme 2

        Parameters
        ----------
        ctx (commands.Context): The command context
        """

        await ctx.reply("https://i.imgur.com/ZqgZEEA.jpg")

    @commands.cooldown(1, 2, commands.BucketType.guild)
    @commands.command()
    async def ifi3(self, ctx: commands.Context):
        """
        ifi meme 3

        Parameters
        ----------
        ctx (commands.Context): The command context
        """

        await ctx.reply("https://i.imgur.com/Gx9DQE5.jpg")

    @commands.cooldown(1, 2, commands.BucketType.guild)
    @commands.command()
    async def uio(self, ctx: commands.Context):
        """
        uio meme 1

        Parameters
        ----------
        ctx (commands.Context): The command context
        """

        await ctx.reply("https://i.imgur.com/188MoIV.jpg")

    @commands.cooldown(1, 2, commands.BucketType.guild)
    @commands.command()
    async def ntnu(self, ctx: commands.Context):
        """
        ntnu meme 1

        Parameters
        ----------
        ctx (commands.Context): The command context
        """

        await ctx.reply("https://twitter.com/NTNU/status/970667413564993536")

    @commands.cooldown(1, 2, commands.BucketType.guild)
    @commands.command()
    async def ntnu2(self, ctx: commands.Context):
        """
        ntnu meme 2

        Parameters
        ----------
        ctx (commands.Context): The command context
        """

        await ctx.reply("https://i.imgur.com/h84fknj.jpg")

    @commands.cooldown(1, 2, commands.BucketType.guild)
    @commands.command()
    async def erna(self, ctx: commands.Context):
        """
        Reply with Erna Solberg's "vil ikke" tweet

        Parameters
        ----------
        ctx (commands.Context): The command context
        """

        await ctx.reply("https://twitter.com/erna_solberg/status/1075333228779765760")

    @commands.cooldown(1, 2, commands.BucketType.guild)
    @commands.command()
    async def dustore(self, ctx: commands.Context):
        """
        dæven døtte sykkelstøtte

        Parameters
        ----------
        ctx (commands.Context): The command context
        """

        await ctx.reply("https://twitter.com/vikingfotball/status/919622148599230465")

    @commands.cooldown(1, 2, commands.BucketType.guild)
    @commands.command()
    async def snake(self, ctx: commands.Context):
        """
        snake

        Parameters
        ----------
        ctx (commands.Context): The command context
        """

        await ctx.reply("A snake eating its own tail indicates that its excrement provides food for it")

    @commands.cooldown(1, 2, commands.BucketType.guild)
    @commands.command()
    async def memes(self, ctx: commands.Context):
        """
        Youtube meme playlist

        Parameters
        ----------
        ctx (commands.Context): The command context
        """

        await ctx.reply("https://youtube.com/playlist?list=PLFV_L_I9qjsoVvh0KT5kHC2_VB8ZGtQoG&si=CpioMM0k3-XTrHCL")

    @commands.cooldown(1, 2, commands.BucketType.guild)
    @commands.command()
    async def hf(self, ctx: commands.Context):
        """
        ekte HF moment

        Parameters
        ----------
        ctx (commands.Context): The command context
        """

        await ctx.reply(
            "https://media.discordapp.net/attachments/811606213665357824/1188473225030680586/Screenshot_2023-12-24-14-28-01-33_a23b203fd3aafc6dcb84e438dda678b6.jpg"
        )

    @commands.cooldown(1, 2, commands.BucketType.guild)
    @commands.command()
    async def infosec(self, ctx: commands.Context):
        """
        infosec er gøy

        Parameters
        ----------
        ctx (commands.Context): The command context
        """

        await ctx.reply(
            "https://cdn.discordapp.com/attachments/816357444724457502/890547766181371954/Snapchat-1979489663.mp4"
        )

    @commands.cooldown(1, 2, commands.BucketType.guild)
    @commands.command()
    async def edb(self, ctx: commands.Context):
        """
        edb er vanskelig

        Parameters
        ----------
        ctx (commands.Context): The command context
        """

        f = discord.File("./src/assets/edb.png")
        await ctx.reply(file=f)


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): The bot instance
    """

    await bot.add_cog(Fun(bot))
