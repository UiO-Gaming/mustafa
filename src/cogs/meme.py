import asyncio
import functools
import os
import subprocess
from io import BytesIO

import cv2
import discord
import numpy as np
import yt_dlp
from discord import app_commands
from discord.ext import commands
from moviepy import CompositeVideoClip
from moviepy import TextClip
from moviepy import VideoFileClip
from moviepy import vfx
from PIL import Image
from PIL import ImageEnhance
from PIL import UnidentifiedImageError

from cogs.utils import discord_utils
from cogs.utils import embed_templates
from cogs.utils import misc_utils


class Meme(commands.Cog):
    """Generate memes"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot

    @app_commands.checks.bot_has_permissions(attach_files=True)
    @app_commands.checks.cooldown(1, 5)
    @app_commands.command(name="deepfry", description="Friter et bilde til hundre og helvete")
    @app_commands.rename(attachment="bilde")
    @app_commands.describe(attachment="Bildet som skal frityrstekes")
    async def deepfry(self, interaction: discord.Interaction, attachment: discord.Attachment):
        """
        Deepfries an image

        Parameters
        ----------
        interaction (discord.Interaction): The interaction
        attachment (discord.Attachment): The image to deepfry
        """

        await interaction.response.defer()

        # Fetch image
        input_image = await discord_utils.get_file_bytesio(attachment)

        try:
            image = Image.open(input_image)
        except UnidentifiedImageError:
            await interaction.followup.send(embed=embed_templates.error_warning("Bildet er ugyldig"))
            return

        output = await asyncio.to_thread(Meme.fry, image)

        await interaction.followup.send(file=discord.File(output, "deepfry.jpg"))

    @staticmethod
    def fry(image: Image.Image) -> BytesIO:
        """
        Applies the deepfrying filters to an image

        Parameters
        ----------
        image (Image.Image): The image to deepfry

        Returns
        ----------
        (BytesIO): The deepfried image as JPEG
        """

        if image.mode != "RGB":
            image = image.convert("RGB")

        # Apply various deepfrying filters
        enhancer = ImageEnhance.Color(image)
        image = enhancer.enhance(2.0)

        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)

        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)

        output = BytesIO()
        image.save(output, format="jpeg", quality=5)
        output.seek(0)

        return output

    @app_commands.checks.bot_has_permissions(attach_files=True)
    @app_commands.checks.cooldown(1, 5)
    @app_commands.command(name="preferansemem", description="Generer en drake-aktig mem basert på tekst")
    @app_commands.rename(bad_text="dårlig_tekst", good_text="bra_tekst")
    @app_commands.describe(bad_text="Teksten øverst, det som er dårlig", good_text="Teksten nederst, det som er bra")
    async def prefer_meme(self, interaction: discord.Interaction, bad_text: str, good_text: str):
        """
        Generates a drake-like meme based on text

        Parameters
        ----------
        interaction (discord.Interaction): The interaction
        bad_text (str): The upper text, what's disliked
        good_text (str): The lower text, what's liked
        """

        await interaction.response.defer()

        output = await asyncio.to_thread(Meme.make_prefer_meme, bad_text, good_text)

        # Send image
        await interaction.followup.send(file=discord.File(output, "sivert_goodbad.jpg"))

    @staticmethod
    def make_prefer_meme(bad_text: str, good_text: str) -> BytesIO:
        """
        Draws the texts on the drake-like meme template

        Parameters
        ----------
        bad_text (str): The upper text, what's disliked
        good_text (str): The lower text, what's liked

        Returns
        ----------
        (BytesIO): The meme as JPEG
        """

        # Fetch meme template
        template = cv2.imread("./src/assets/sivert_goodbad.jpg")

        # Draw text
        font = "./src/assets/fonts/comic.ttf"
        misc_utils.put_text_in_box(template, bad_text, (540, 0), (1080, 540), font)
        misc_utils.put_text_in_box(template, good_text, (540, 540), (1080, 1080), font)

        # Save image to buffer
        _, buffer = cv2.imencode(".jpg", template)
        output = BytesIO(buffer)
        cv2.imdecode(np.frombuffer(output.getbuffer(), np.uint8), -1)
        output.seek(0)

        return output

    @app_commands.checks.bot_has_permissions(embed_links=True, attach_files=True)
    @app_commands.checks.cooldown(1, 5)
    @app_commands.command(name="wojakpoint", description="Få UiO Gaming-medlemmer til å peke på et bilde")
    @app_commands.rename(attachment="bilde")
    @app_commands.describe(attachment="Bildet som det skal pekes på. Kun PNG og JPG")
    async def wojakpoint(self, interaction: discord.Interaction, attachment: discord.Attachment):
        """
        Make glorious UiO Gaming members point at your desired picture

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        attachment (discord.Attachment): The image to point at. Only supports png and jpg for now
        """

        await interaction.response.defer()

        if attachment.content_type not in ["image/png", "image/jpeg"]:
            embed = embed_templates.error_warning("Bildet må være i PNG- eller JPEG-format")
            return await interaction.followup.send(embed=embed)

        provided_image = await discord_utils.get_file_bytesio(attachment)
        output = await asyncio.to_thread(Meme.make_wojakpoint, provided_image)

        # Send
        f = discord.File(output, filename="uio_wojak.png")
        embed = discord.Embed()
        embed.set_image(url="attachment://uio_wojak.png")
        await interaction.followup.send(embed=embed, file=f)

    @staticmethod
    def make_wojakpoint(provided_image: BytesIO) -> BytesIO:
        """
        Puts the pointing wojaks on top of an image

        Parameters
        ----------
        provided_image (BytesIO): The image to point at

        Returns
        ----------
        (BytesIO): The meme as PNG
        """

        # Prepare template
        template = Image.open("./src/assets/wojak_point.png").convert("RGBA")

        provided_image = Image.open(provided_image).convert("RGBA").resize((template.width, template.height))

        # Putting it all together
        # We paste at the bottom of the image even though it's not necessary in this case
        # Keeping it in case we want to change croppoing and sizing behaviour in the future
        provided_image.paste(template, (0, provided_image.height - template.height), template)

        # Save image
        output = BytesIO()
        provided_image.save(output, format="PNG")
        output.seek(0)

        return output

    # I can't be arsed to make this code good rn
    # This code is absolute horse ass
    # TODO:: improve this
    @app_commands.checks.bot_has_permissions(attach_files=True)
    @app_commands.checks.cooldown(1, 30)
    @app_commands.command(name="nightcore", description="nightcore en gitt lyd")
    @app_commands.rename(query="søk")
    @app_commands.describe(query="Søkeord for å finne lyden på YouTube", url="Lenke til lyden")
    async def nightcore(self, interaction: discord.Interaction, query: str = None, url: str = None):
        """
        Turn the user passed url or searched media into nightcore

        Parameters
        ----------
        interaction (discord.Interaction): The interaction
        query (str|None): Search term to look up the media on YouTube
        url (str|None): Link to the source media
        """

        await interaction.response.defer()

        if not url and not query:
            return await interaction.followup.send(
                embed=embed_templates.error_warning("Du må enten gi meg en link eller noe å søke etter"),
                ephemeral=True,
            )

        max_seconds = 3600

        def duration_filter(info_dict, *, incomplete):
            """Filters out videos longer than the specified limit."""
            duration = info_dict.get("duration")
            if duration and duration > max_seconds:
                return f"Skipping: Video is too long ({duration} seconds)"
            return None

        # make sure the url is used if both variables are used
        pre_nightcored = f"./src/assets/temp/{interaction.user.id}_pre_nightcore"
        options = {
            "format": "bestaudio/best",
            "default_search": "ytsearch",
            "noplaylist": True,
            "allowed_extractors": ["default", "-generic"],
            "match_filter": duration_filter,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "outtmpl": f"{pre_nightcored}",
            "quiet": True,
            "no_warnings": True,
        }
        prefix = "ytsearch1:" if not url else ""
        search_term = query if not url else url

        def download():
            with yt_dlp.YoutubeDL(options) as ydl:
                return ydl.extract_info(f"{prefix}{search_term}", download=True)

        try:
            info = await asyncio.to_thread(download)
        except Exception as e:
            self.bot.logger.warning(f"Failed to download media {e}")
            return await interaction.followup.send(
                embed=embed_templates.error_fatal("Klarte ikke å laste ned den forespurte sangen!"),
            )

        # AAAAAAAAAAAAAAA MY EYES
        if "entries" in info:
            info = info["entries"][0] if info["entries"] else None
        if not info or not info.get("duration") or info.get("duration") > max_seconds:
            return await interaction.followup.send(
                embed=embed_templates.error_warning(
                    "Fant ingen gyldig lyd (kan være for lang eller utilgjengelig)."
                    + "Jeg er for lat til å fikse noe ordentlig"
                ),
                ephemeral=True,
            )

        nightcored = f"./src/assets/temp/{interaction.user.id}_nightcore.mp3"
        command = [
            "ffmpeg",
            "-loglevel",
            "error",
            "-i",
            f"{pre_nightcored}.mp3",
            "-af",
            "asetrate=44100*1.33,atempo=1,aresample=44100,bass=g=6:f=100:w=0.5,volume=0.8",
            nightcored,
            "-y",  # Overwrite if exists
        ]

        try:
            await asyncio.to_thread(subprocess.run, command, check=True)
            self.bot.logger.info(f"Successfully created nightcorified song at {nightcored}")
        except subprocess.CalledProcessError as e:
            self.bot.logger.error(f"Error during conversion: {e}")
            await interaction.followup.send(embed=embed_templates.error_fatal("Klarte ikke å nightcore sangen!"))
        else:
            try:
                await interaction.followup.send(file=discord.File(nightcored))
            except discord.errors.HTTPException:
                self.bot.logger.warning(f"Failed to send temporary file {nightcored}")
                await interaction.followup.send(
                    embed=embed_templates.error_warning("Failed to send file. It is probably too big."),
                    ephemeral=True,
                )

        for temp_file in (nightcored, f"{pre_nightcored}.mp3"):
            try:
                os.remove(temp_file)
            except (FileNotFoundError, PermissionError):
                self.bot.logger.warning(f"Failed to remove temporary file {temp_file}")

    @app_commands.checks.bot_has_permissions(attach_files=True)
    @app_commands.checks.cooldown(1, 60)
    @app_commands.command(name="crabrave", description="Generer en crab rave video basert på tekst")
    @app_commands.rename(top_text="topptekst", bottom_text="bunntekst")
    @app_commands.describe(top_text="Teksten øverst", bottom_text="Teksten nederst")
    async def crab_rave(self, interaction: discord.Interaction, top_text: str, bottom_text: str):
        """
        Generates a crab rave video based on text

        Parameters
        ----------
        interaction (discord.Interaction): The interaction
        top_text (str): The upper text
        bottom_text (str): The lower text
        """

        await interaction.response.defer()

        generation_task = functools.partial(Meme.make_crab, top_text, bottom_text, interaction.user.id)
        await self.bot.loop.run_in_executor(None, generation_task)

        temp_file = f"./src/assets/temp/{interaction.user.id}_crab.mp4"
        try:
            await interaction.followup.send(file=discord.File(temp_file))
        except discord.errors.HTTPException:
            self.bot.logger.warning(f"Failed to send temporary file {temp_file}")
            await interaction.followup.send(
                embed=embed_templates.error_warning("Failed to send video. File is probably too big."),
                ephemeral=True,
            )

        try:
            os.remove(temp_file)
        except (FileNotFoundError, PermissionError):
            self.bot.logger.warning(f"Failed to remove temporary file {temp_file}")

    @staticmethod
    def make_crab(top_text: str, bottom_text: str, user_id: int):
        """
        Generates a crab rave video based on text
        Is it really stolen code if the copilot stole it for me?

        Parameters
        ----------
        top_text (str): The upper text
        bottom_text (str): The lower text
        user_id (int): The user ID
        """

        clip = VideoFileClip("./src/assets/crab.mp4")

        top_part = (
            TextClip(text=top_text, font_size=60, color="white", stroke_width=2, stroke_color="black")
            .with_start(11.0)
            .with_position(("center", 300))
            .with_duration(26.0)
        )
        middle_part = (
            TextClip(
                text="____________________",
                font_size=48,
                color="white",
            )
            .with_start(11.0)
            .with_position(("center", "center"))
            .with_duration(26.0)
        )
        bottom_part = (
            TextClip(text=bottom_text, font_size=60, color="white", stroke_width=2, stroke_color="black")
            .with_start(11.0)
            .with_position(("center", 400))
            .with_duration(26.0)
        )

        top_part = top_part.with_effects([vfx.CrossFadeIn(1)])
        middle_part = middle_part.with_effects([vfx.CrossFadeIn(1)])
        bottom_part = bottom_part.with_effects([vfx.CrossFadeIn(1)])

        video = CompositeVideoClip(
            [
                clip,
                top_part,
                middle_part,
                bottom_part,
            ]
        ).with_duration(26.0)

        video.write_videofile(
            f"./src/assets/temp/{user_id}_crab.mp4",
            preset="superfast",
            logger=None,
        )
        clip.close()
        video.close()


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): The bot instance
    """

    await bot.add_cog(Meme(bot))
