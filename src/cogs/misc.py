import random
import re
from datetime import datetime
from hashlib import md5
from io import BytesIO

import dateparser
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
    @app_commands.command(name="mennesketid", description="Konverter tid i menneskelig format til dato og klokkeslett")
    async def humantime(self, interaction: discord.Interaction, tekst: str):
        """
        Convert human-readable time to date and time

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        tekst (str): Human-readable time string
        """

        parsed_time = dateparser.parse(
            tekst,
            languages=["nb", "nn", "en"],
        )
        if not parsed_time:
            embed = embed_templates.error_warning("Forstod ikke tidspunktet. Prøv å skrive det på en annen måte.")
            return await interaction.response.send_message(embed=embed)

        timestamp = discord.utils.format_dt(parsed_time, style="F")
        await interaction.response.send_message(timestamp)

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

    @app_commands.checks.cooldown(1, 2)
    @app_commands.command(name="cs2excuse", description="Generates excuses for not shooting heads")
    async def cs2excuse(self, interaction: discord.Interaction):
        """
        When you're being a weak mf and don't want to shoot heads.

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        excuses = [
            "I'm tired",
            "I have a headache",
            "I am hungover and might puke mid-game",
            "I just need to jerk off first",
            "I'm pretending to study",
            "I need to eat, my aim isn't as good when I'm hungry",
            "I'm worried Markus will teamkill me",
            "I'm terrified of Dust II",
            "I have explosive diarrhea",
            "I have converted to pacifism",
        ]

        random_excuse = random.choice(excuses)

        await interaction.response.send_message(random_excuse)

    @app_commands.checks.cooldown(1, 2)
    @app_commands.command(name="bushism", description="Generates a random George W. Bush quote")
    async def bushism(self, interaction: discord.Interaction):
        """
        The 43rd President of the United States is responsible for countless words of wisdom.

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        bushisms = [
            "I think we agree, the past is over.",
            "We can have filters on Internets where public money is spent.",
            "They misunderestimated me.",
            "I know the human being and fish can coexist peacefully.",
            "Families is where nations find hope, where wings take dream.",
            ("There's an old saying in Tennessee—I know it's in Texas," 
             "probably in Tennessee—that says, 'Fool me once, shame on... "
             "shame on you.' Fool me—you can't get fooled again."),
            ("Too many good docs are getting out of the business. "
             "Too many OB-GYNs aren't able to practice their love "
             "with women all across this country."),
            ("I'm going to put people in my place, so when the history of "
             "this administration is written at least there's an authoritarian "
             "voice saying exactly what happened."),
            ("See, in my line of work you got to keep repeating things over "
             "and over and over again for the truth to sink in, to kind of "
             "catapult the propaganda."),
            ("I'll be long gone before some smart person ever figures out "
             "what happened inside this Oval Office."),
            ("Tribal sovereignty means that: It’s sovereign. It’s- you’re a..." 
             "you’re a… you’ve been given sovereignty, and you’re viewed… as a "
             "sovereign entity. And, therefore, the relationship between the "
             "Federal government and… Tribes is one between sovereign entities."),
            ("I'm the commander, see. I don't need to explain—I do not need to "
             "explain why I say things. That's the interesting thing about being "
             "the President. Maybe somebody needs to explain to me why they say "
             "something, but I don't feel like I owe anybody an explanation."),
            ("I was proud the other day when both Republicans and Democrats stood "
             "with me in the Rose Garden to announce their support for a clear "
             "statement of purpose: you disarm, or we will."),
            ("Yesterday, you made note of my—the lack of my talent when it came "
             "to dancing. But nevertheless, I want you to know I danced with joy. "
             "And no question Liberia has gone through very difficult times."),
            ("This is still a dangerous world. It's a world of madmen and "
             "uncertainty and potential mental losses."),
            ("Our enemies are innovative and resourceful, and so are we. "
             "They never stop thinking about new ways to harm our country "
             "and our people, and neither do we."),
            ("I'm telling you there's an enemy that would like to attack "
             "America, Americans, again. There just is. That's the reality "
             "of the world. And I wish him all the very best."),
            ("Well, I mean that a defeat in Iraq will embolden the enemy "
             "and will provide the enemy—more opportunity to train, plan, "
             "to attack us. That's what I mean. There— it's— you know, one "
             "of the hardest parts of my job is to connect Iraq to the war "
             "on terror."),
            ("I just want you to know that, when we talk about war, "
             "we're really talking about peace."),
            ("We must stop the terror. I call upon all nations, to do "
             "everything they can, to stop these terrorist killers. "
             "Thank you... now watch this drive."),
            ("The decision of one man [Vladimir Putin], to launch a "
             "wholly unjustified and brutal invasion of Iraq. I mean, "
             "of Ukraine. Iraq too."),
            ("When you think about it, in the first month of the new year "
             "there will be an election in the Palestinian Territory and "
             "there will be an election in Iraq. Who could have possibly "
             "envisioned an erection— an election in Iraq?"),
            ("You bet I cut the taxes at the top. That encourages entrepreneurship. "
             "What we Republicans should stand for is growth in the economy. "
             "We ought to make the pie higher."),
            ("If you're a single mother with two children—which is the toughest job "
             "in America, as far as I'm concerned—you're working hard to put food "
             "on your family."),
            ("You work three jobs? ... Uniquely American, isn't it? I mean, that is "
             "fantastic that you're doing that."),
            "Rarely is the question asked: is our children learning?",
            "You teach a child to read, and he or her will be able to pass a literacy test.",
            ("As yesterday's positive report card shows, childrens do learn, when standards "
            "are high and results are measured.")
        ]

        random_bushism = random.choice(bushisms)

        await interaction.response.send_message(random_bushism)


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(Misc(bot))
