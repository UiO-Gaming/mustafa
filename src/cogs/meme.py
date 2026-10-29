import asyncio
import functools
import os
import subprocess
import tempfile
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

NIGHTCORE_SPEED = 1.33
# Resample first so the speed-up is the same whatever the source's sample rate is
NIGHTCORE_FILTER = f"aresample=44100,asetrate=44100*{NIGHTCORE_SPEED},aresample=44100,bass=g=6:f=100:w=0.5,volume=0.8"
MP3_BITRATES = [192, 160, 128, 112, 96, 80, 64]


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

    @staticmethod
    def nightcore_bitrate(duration: float, filesize_limit: int) -> int | None:
        """
        Get the highest MP3 bitrate that keeps a nightcored song within the upload limit

        Parameters
        ----------
        duration (float): The duration of the original song in seconds
        filesize_limit (int): The maximum file size in bytes

        Returns
        ----------
        (int | None): The bitrate in kbps. None if the song is too long even at the lowest bitrate
        """

        # Leave some room for the MP3 headers
        max_bits = filesize_limit * 8 * 0.95
        output_duration = duration / NIGHTCORE_SPEED
        return next((kbps for kbps in MP3_BITRATES if kbps * 1000 * output_duration <= max_bits), None)

    @staticmethod
    def download_audio(target: str, directory: str, filesize_limit: int) -> dict | None:
        """
        Download the audio of a song, unless it's too long to send as nightcore

        Parameters
        ----------
        target (str): A link to the song or a yt-dlp search
        directory (str): The directory to download to
        filesize_limit (int): The maximum file size of the nightcored song in bytes

        Returns
        ----------
        (dict | None): The yt-dlp info of the downloaded song. None if nothing was found or it's too long
        """

        options = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "allowed_extractors": ["default", "-generic"],
            "outtmpl": os.path.join(directory, "source.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
        }

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(target, download=False)
            if "entries" in info:
                info = next(iter(info["entries"]), None)

            if not info or not info.get("duration") or not Meme.nightcore_bitrate(info["duration"], filesize_limit):
                return None

            return ydl.process_ie_result(info, download=True)

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
        url (str|None): Link to the source media. Used instead of the search term if both are given
        """

        if not url and not query:
            return await interaction.response.send_message(
                embed=embed_templates.error_warning("Du må enten gi meg en link eller noe å søke etter"),
                ephemeral=True,
            )

        await interaction.response.defer()

        with tempfile.TemporaryDirectory(dir="./src/assets/temp") as directory:
            target = url or f"ytsearch1:{query}"
            try:
                info = await asyncio.to_thread(Meme.download_audio, target, directory, interaction.filesize_limit)
            except yt_dlp.utils.DownloadError as e:
                self.bot.logger.warning(f"Failed to download {target}: {e}")
                return await interaction.followup.send(
                    embed=embed_templates.error_fatal("Klarte ikke å laste ned den forespurte sangen!")
                )

            if not info:
                return await interaction.followup.send(
                    embed=embed_templates.error_warning("Fant ingen lyd, eller så er den for lang til å sendes")
                )

            bitrate = Meme.nightcore_bitrate(info["duration"], interaction.filesize_limit)
            nightcored = os.path.join(directory, "nightcore.mp3")
            command = [
                "ffmpeg",
                "-loglevel",
                "error",
                "-i",
                info["requested_downloads"][0]["filepath"],
                "-af",
                NIGHTCORE_FILTER,
                "-b:a",
                f"{bitrate}k",
                nightcored,
            ]

            try:
                await asyncio.to_thread(subprocess.run, command, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                self.bot.logger.error(f"Failed to nightcore {target}: {e.stderr}")
                return await interaction.followup.send(
                    embed=embed_templates.error_fatal("Klarte ikke å nightcore sangen!")
                )

            try:
                await interaction.followup.send(
                    content=discord.utils.escape_markdown(info.get("title", "")),
                    file=discord.File(nightcored, filename="nightcore.mp3"),
                )
            except discord.HTTPException as e:
                self.bot.logger.warning(f"Failed to send nightcored {target}: {e}")
                await interaction.followup.send(embed=embed_templates.error_fatal("Klarte ikke å sende filen"))

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
