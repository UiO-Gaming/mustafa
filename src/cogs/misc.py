import random
import re
from datetime import datetime
from hashlib import md5
from io import BytesIO

import discord
import requests
from discord import app_commands
from discord.ext import commands
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

from cogs.utils import discord_utils
from cogs.utils import embed_templates


class Misc(commands.Cog):
    """Miscellaneous commands that don't fit anywhere else"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot

    @app_commands.checks.cooldown(1, 2)
    @app_commands.command(name="weeb", description="Kjeft på weebs")
    async def weeb(self, interaction: discord.Interaction):
        """
        Call out weebs

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        await interaction.response.send_message("<:sven:762725919604473866> Weebs 👉 <#803596668129509417>")

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @app_commands.command(name="owo", description="Oversetter teksten din til owo (we_eb)")
    async def owo(self, interaction: discord.Interaction, tekst: str):
        """
        Translate text into owo (we_eb)

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        tekst (str): Text to translate
        """

        # Decades of computer sciencetist optimizng every little detail to make
        # our computers as fast as possible. Only for me to ruin it by doing this shit.
        # I am sorry to our forefathers whose shoulders we stand upon.
        # I have sinned
        tekst = re.sub(r"[rl]", "w", tekst)
        tekst = re.sub(r"[RL]", "W", tekst)
        tekst = re.sub(r"n([aeiou])", r"ny\1", tekst, flags=re.IGNORECASE)
        tekst = re.sub(r"N([aeiou])", r"Ny\1", tekst)
        tekst = re.sub(r"th", "d", tekst, flags=re.IGNORECASE)
        tekst = tekst.replace("ove", "uv")

        # TODO: add kaomoji? https://kaomoji.moe/

        if len(tekst) >= 1000:
            embed = embed_templates.error_warning("Teksten er for lang")
            return await interaction.response.send_message(embed=embed)

        embed = discord.Embed(description=tekst)
        await interaction.response.send_message(embed=embed)

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @app_commands.command(name="dicksize", description="Se hvor liten pikk du har")
    async def dicksize(self, interaction: discord.Interaction, bruker: discord.Member | discord.User | None = None):
        """
        Get a totally accurate meassurement of a user's dick

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        bruker (discord.Member | discord.User | None): The user you want to see the dicksize of. Defaults to author
        """

        if not bruker:
            bruker = interaction.user

        # Må jo gi meg selv en stor kuk
        if bruker.id == 170506717140877312:
            dick_size = 69
        elif bruker.id == 327207142681608192:
            dick_size = 1
        else:
            dick_hash = md5(str(bruker.id).encode("utf-8")).hexdigest()
            dick_size = (
                int(dick_hash[11:13], 16) * (25 - 2) // 255 + 2
            )  # This is 5 year old code. I have no fucking idea what's going on

        dick_drawing = "=" * dick_size

        embed = discord.Embed(color=bruker.color)
        embed.set_author(name=bruker.global_name, icon_url=bruker.avatar)
        embed.add_field(name="Kukstørrelse", value=f"{dick_size} cm\n8{dick_drawing}D")
        await interaction.response.send_message(embed=embed)

    @app_commands.checks.cooldown(1, 5)
    @app_commands.command(name="emne", description="For NTNU'ere som ikke kan emnekoder på UiO")
    async def course_code(self, interaction: discord.Interaction, emnekode: str):
        """
        Translate UiO course codes to their respective course names

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        emnekode (str): UiO course code
        """

        params = {"action": "autocomplete", "service": "emner", "scope": "/studier/emner", "q": emnekode, "limit": 1}
        data = requests.get("https://www.uio.no/studier/", params=params, timeout=10)
        if data.status_code != 200:
            return await interaction.response.send_message(embed=embed_templates.error_fatal("Kunne ikke nå API"))

        results = data.text.strip("\n").split("\n")[:-1]
        if not results:
            return await interaction.response.send_message(embed=embed_templates.error_warning("Fant ikke emnekode"))

        for result in results:
            code, name, _ = result.split(";")
            if code.lower() == emnekode.lower():
                break

        await interaction.response.send_message(name)

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @app_commands.command(name="klappifiser", description="Klappifiser tekst")
    async def clapify(self, interation: discord.Interaction, tekst: str):
        """
        Add clap emoji between every word of a string

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        tekst (str): Text to clapify
        """

        if len(tekst) >= 1000:
            embed = embed_templates.error_warning("Teksten er for lang")
            return await interation.response.send_message(embed=embed)

        tekst = tekst.replace(" ", "👏")

        embed = discord.Embed(color=interation.client.user.color, description=f"**{tekst.upper()}**")
        await interation.response.send_message(embed=embed)

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @app_commands.command(name="mock", description="vEt dU iKkE hVa mOcKtEkSt eR eLlEr?")
    async def mock(self, interation: discord.Interaction, tekst: str, bruker: discord.User | None = None):
        """
        dO i rEaLlY nEeD tO eXpLaIn??

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        tekst (str): Text to clapify
        """

        # TODO: make this not horrible. I can't be botherd to right now
        words = tekst.split(" ")
        for i, word in enumerate(words):
            karakter = 0
            word = list(word)
            for j, char in enumerate(word):
                if char.isalpha():
                    if karakter % 2 == 0:
                        word[j] = char.lower()
                    else:
                        word[j] = char.upper()
                    karakter += 1
            words[i] = "".join(word)

        text = " ".join(words)
        mention = bruker.mention if bruker else ""

        embed = discord.Embed(color=interation.client.user.color, description=text)
        await interation.response.send_message(content=mention, embed=embed)

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 5)
    @app_commands.command(name="helligdager", description="Se helligdager i et land for et år")
    async def holidays(self, interaction: discord.Interaction, *, land: str = "NO", år: int = None):
        """
        Get holidays for a country for a given year

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        land (str): Country code
        år (int): Year
        """

        land = land.upper()
        år = datetime.now().year if not år else int(år)

        data = requests.get(f"https://date.nager.at/api/v3/publicholidays/{år}/{land}", timeout=10)
        if data.status_code != 200:
            embed = embed_templates.error_warning("Ugyldig land\nHusk å bruke landskoder\n" + "For eksempel: `NO`")
            return await interaction.response.send_message(embed=embed)

        data = data.json()

        country = data[0]["countryCode"].lower()

        # Construct output
        holiday_str = ""
        for day in data:
            date = discord.utils.format_dt(datetime.strptime(day["date"], "%Y-%m-%d"), style="D")
            holiday_str += f'* **{date}**: {day["localName"]}\n'

        embed = discord.Embed(
            color=interaction.client.user.color, title=f":flag_{country}: Helligdager {år} :flag_{country}:"
        )
        embed.description = holiday_str
        await interaction.response.send_message(embed=embed)

    @app_commands.checks.bot_has_permissions(embed_links=True, attach_files=True)
    @app_commands.checks.cooldown(1, 5)
    @app_commands.command(name="match", description="Se hvor mye du matcher med en annen")
    async def match(self, interaction: discord.Interaction, bruker: discord.Member):
        """
        Get dating compatibility with another user

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        bruker (discord.Member): User to match with
        """

        if bruker == interaction.user:
            embed = embed_templates.error_warning("Jeg vet du er ensom, men du kan ikke matche med deg selv")
            return await interaction.response.send_message(embed=embed)

        invoker_id = int(str(interaction.user.id)[11:14])
        user_id = int(str(bruker.id)[11:14])

        match_percent = int((invoker_id + user_id) % 100)

        if bruker.id == self.bot.user.id:
            match_percent = 100

        # Prepare invoker avatar
        invoker_avatar = await discord_utils.get_file_bytesio(interaction.user.display_avatar)
        invoker = Image.open(invoker_avatar).convert("RGBA")
        invoker = invoker.resize((389, 389))

        # Prepare user avatar
        user_avatar = await discord_utils.get_file_bytesio(bruker.display_avatar)
        user = Image.open(user_avatar).convert("RGBA")
        user = user.resize((389, 389))

        # Prepare heart image
        heart = Image.open("./src/assets/heart.png")
        mask = Image.open("./src/assets/heart.png", "r")

        # Putting it all together
        image = Image.new("RGBA", (1024, 576))
        image.paste(invoker, (0, 94))
        image.paste(user, (635, 94))
        image.paste(heart, (311, 94), mask=mask)
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype("./src/assets/fonts/comic.ttf", 86)
        font_size = font.getbbox(f"{match_percent}%")
        font_size = ((image.size[0] - font_size[2]) / 2, (image.size[1] - font_size[3]) / 2)
        draw.text(font_size, f"{match_percent}%", font=font, fill=(255, 255, 255, 255))

        # Save image
        output = BytesIO()
        image.save(output, format="PNG")
        output.seek(0)

        # Send
        f = discord.File(output, filename=f"{interaction.user.id}_{bruker.id}_match.png")
        embed = discord.Embed()
        embed.set_image(url=f"attachment://{interaction.user.id}_{bruker.id}_match.png")
        await interaction.response.send_message(embed=embed, file=f)

    @app_commands.checks.cooldown(1, 2)
    @app_commands.command(name="ifonlyyouknew", description="How bad things really are")
    async def howbadthingsreallyare(self, interaction: discord.Interaction):
        """
        If only you knew how bad things really are.

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        links = [
            "https://cdn.discordapp.com/attachments/747542544291987597/973603487541772369/leanderbad.png",
            "https://cdn.discordapp.com/attachments/747542544291987597/973603305467043850/unknown.png",
            "https://cdn.discordapp.com/attachments/811606213665357824/955206225681875015/73D1B4ED-BD2E-4BCB-9032-67BF9AEAF4B2.jpg",
            "https://cdn.discordapp.com/attachments/811606213665357824/987321261690605618/Snapchat-1438586183.jpg",
            "https://cdn.discordapp.com/attachments/747542544291987599/1288403959299706901/unknown-171.png",
        ]

        random_link = random.choice(links)

        await interaction.response.send_message(random_link)

    @app_commands.checks.cooldown(1, 2)
    @app_commands.command(name="coinflip", description="Kron eller mynt?")
    async def coinflip(self, interaction: discord.Interaction):
        """
        Flip a coin

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        random_result = random.randint(1, 100)  # We use 1 and not 0 to avoid a tie
        if random_result > 50:  # And by including 50 we avoid that tie
            outcome = "Kron"
        elif random_result <= 50:
            outcome = "Mynt"

        await interaction.response.send_message(outcome)

    @app_commands.checks.cooldown(1, 2)
    @app_commands.command(name="smellynerds", description="MAKE AN EXE FILE")
    async def smellynerds(self, interaction: discord.Interaction):
        """
        Github copypasta

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        copypasta = (
            "I DONT GIVE A FUCK ABOUT THE FUCKING CODE! i just want to download this stupid "
            "fucking application and use it\n"
            "WHY IS THERE CODE??? MAKE A FUCKING .EXE FILE AND GIVE IT TO ME. these dumbfucks "
            "think that everyone is a developer and understands code. well i am not and i "
            "don't understand it. I only know to download and install applications. SO WHY "
            "THE FUCK IS THERE CODE? make an EXE file and give it to me. STUPID FUCKING SMELLY NERDS"
        )

        await interaction.response.send_message(copypasta)


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(Misc(bot))
