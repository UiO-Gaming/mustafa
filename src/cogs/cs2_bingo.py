import asyncio
import json
import random
from datetime import datetime
from datetime import timedelta

import cv2
import discord
import numpy as np
from discord import app_commands
from discord.ext import commands
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

from cogs.utils import discord_utils
from cogs.utils import embed_templates


class CS2Bingo(commands.Cog):
    """Join lobbies and generate bingo sheets for CS2"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot
        self.active_lobbies = {}

    bingo_group = app_commands.Group(name="cs2bingo", description="Bingo commands for CS2")

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 10)
    @bingo_group.command(name="lag", description="Lag en bingolobby")
    async def bingo_create(self, interaction: discord.Interaction):
        """
        Create a bingo lobby

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        if lobby := self.active_lobbies.get(str(interaction.user.id), None):
            if lobby["ends"] < datetime.now():
                self.active_lobbies.pop(str(interaction.user.id))
            else:
                return await interaction.response.send_message(
                    embed=embed_templates.error_warning(
                        interaction,
                        text="Du hoster allerede en lobby",
                    )
                )

        for lobby in self.active_lobbies.values():
            if interaction.user.id in lobby["players"]:
                return await interaction.response.send_message(
                    embed=embed_templates.error_warning(
                        interaction,
                        text="Du er allerede i en lobby",
                    )
                )

        self.active_lobbies[str(interaction.user.id)] = {
            "host": interaction.user,
            "players": [interaction.user],
            "ends": datetime.now() + timedelta(minutes=10),
            "kicked_players": [],
        }

        time_left = discord.utils.format_dt(self.active_lobbies[str(interaction.user.id)]["ends"], "R")

        embed = discord.Embed(
            title="Bingolobby",
            description=f"Lobbyen stenger {time_left}. Bli med innen da!",
            color=discord_utils.get_color(interaction.user),
        )
        embed.set_author(name=interaction.user.global_name, icon_url=interaction.user.avatar)
        embed.add_field(name="Spillere", value=f"* {interaction.user.mention}", inline=False)
        await interaction.response.send_message(
            embed=embed, view=BingoView(self.active_lobbies[str(interaction.user.id)])
        )


class BingoGenerator:
    """
    Generate bingo sheets for CS2
    """

    BINGO_PATH = "./src/assets/cs2_bingo"
    with open(f"{BINGO_PATH}/cells.json") as f:
        cells = json.load(f)
    FONT_PATH = "./src/assets/fonts/comic.ttf"

    @classmethod
    async def put_text_in_box(
        cls,
        image: np.ndarray,
        text: str,
        top_left: tuple,
        bottom_right: tuple,
        font_path: str,
        font_size: int = 20,
        color: tuple = (0, 0, 0),
    ):
        """
        Puts text inside a bounding box on the cv2 image with automatic text wrapping, using PIL for text rendering.

        :param image: Source cv2 image (numpy array).
        :param text: Text string to be put.
        :param top_left: Tuple (x, y) defining the top-left corner of the bounding box.
        :param bottom_right: Tuple (x, y) defining the bottom-right corner of the bounding box.
        :param font_path: Path to a .ttf font file.
        :param font_size: Initial font size.
        :param color: Text color in RGB.
        :return: Image with text (numpy array).
        """

        # Convert the cv2 image to a PIL image
        image_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(image_pil)
        font = ImageFont.truetype(font_path, font_size)

        # Calculate text size and wrapping
        x1, y1 = top_left
        x2, y2 = bottom_right
        w, _ = x2 - x1, y2 - y1
        lines = []
        line = []

        for word in text.split():
            # Check if adding the word to the line would exceed the width
            line_width = draw.textlength(" ".join(line + [word]), font=font)
            if line_width <= w:
                line.append(word)
            else:
                lines.append(" ".join(line))
                line = [word]

        # Add the last line
        lines.append(" ".join(line))

        # Draw text
        y = y1
        for line in lines:
            draw.text((x1, y), line, fill=color, font=font)
            y += font.getlength(line)

        # Convert back to cv2 image format and update the original image
        cv2_image = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)
        np.copyto(image, cv2_image)

    @classmethod
    async def sample_cells(cls, players: list[str]) -> dict[str, list[str]]:
        assert 0 < len(players) <= 6  # TODO: fix?

        default_space = cls.cells["all"]

        if len(players) < 5:
            default_space += cls.cells["randoms"]

        player_cells = {}

        for player in players:
            other_players = players.copy()
            other_players.remove(player)
            player_space = default_space + [i for op in other_players for i in cls.cells.get(op, [])]
            other_players.append("du")
            player_space += [s.format(random.choice(other_players)) for s in cls.cells["parameterized"]]

            sampled_cells = np.random.choice(player_space, replace=False, size=25)
            player_cells[player] = list(sampled_cells)

        return player_cells

    @classmethod
    async def generate_sheets(cls, players: list[discord.Member]):
        """
        Generate bingo sheets for each player

        Parameters
        ----------
        players (list[str]): List of the player's discord IDs as strings
        """

        players = [str(p.id) for p in players]

        sample_space = await cls.sample_cells(players)
        assert len(sample_space) == len(players)
        image = cv2.imread(f"{cls.BINGO_PATH}/cs2_bingo_sheet.png")

        player_sheets = {}

        for player in players:
            player_sheets[player] = await cls.generate_sheet(sample_space[player], image)

        for p, sheet in player_sheets.items():
            cv2.imwrite(f"./src/assets/temp/{p}_bingo.png", sheet)

    @classmethod
    async def generate_sheet(cls, sample_space: list, image: np.ndarray):
        image = image.copy()

        # start = 8, 294
        # end = 625, 910

        sliced = image[295:910, 10:625]
        # patches = []

        for i in range(0, 5):
            for j in range(0, 5):
                width = 123
                await cls.put_text_in_box(
                    sliced,
                    sample_space.pop(),
                    (i * width + 1, j * width + 1),
                    ((i + 1) * width, (j + 1) * width),
                    font_path=cls.FONT_PATH,
                )

        return image


class BingoView(discord.ui.View):
    def __init__(self, lobby: dict):
        lobby_end = (lobby.get("ends") - datetime.now()).total_seconds()
        super().__init__(timeout=lobby_end)

        self.lobby = lobby

        self.add_item(KickSelectMenu(self.lobby, self))

    async def on_timeout(self):
        await self.end_lobby()

    async def end_lobby(self, interaction):
        self.lobby["ends"] = datetime.now()
        for item in self.children:
            item.disabled = True

    async def rerender_players(self, interaction: discord.Interaction):
        self.children[-1].options = [
            discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🔨") for p in self.lobby["players"]
        ]
        embed = interaction.message.embeds[0].set_field_at(
            0, name="Spillere", value="\n".join([f"* {p.mention}" for p in self.lobby["players"]])
        )
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Bli med", style=discord.ButtonStyle.blurple)
    async def join_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
        if datetime.now() > self.lobby["ends"]:
            embed = embed_templates.error_warning(interaction, text="Lobbyen har allerede startet")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if (
            interaction.user.id in self.lobby["kicked_players"]
        ):  # We have to use the ID here to avoid fetching the member object in the selection menu
            embed = embed_templates.error_warning(interaction, text="Du er blitt sparket fra lobbyen")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if interaction.user in self.lobby["players"]:
            embed = embed_templates.error_warning(interaction, text="Du er allerede i lobbyen")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        self.lobby["players"].append(interaction.user)
        await self.rerender_players(interaction)

        await interaction.response.send_message(
            embed=embed_templates.success(interaction, text="Du har blitt med i lobbyen"), ephemeral=True
        )

    @discord.ui.button(label="Start", style=discord.ButtonStyle.green)
    async def start_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.lobby["host"]:
            embed = embed_templates.error_warning(interaction, text="Bare hosten kan starte bingoen")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        await self.end_lobby(interaction)

        embed = interaction.message.embeds[0]
        embed.description = "Bingoen har startet!"
        await interaction.message.edit(embed=embed, view=self)

        mention_players = " ".join([f"{p.mention}" for p in self.lobby["players"]])
        embed = embed_templates.success(
            interaction,
            text="Bingoen har startet\n\nDere vil nå få tilsendt bingobrettene deres på DM."
            + "Sørg for at jeg kan slide inn i dem :smirk:",
        )
        await interaction.response.send_message(content=mention_players, embed=embed)

        await BingoGenerator.generate_sheets(self.lobby["players"])
        for player in self.lobby["players"]:
            try:
                await player.send(file=discord.File(f"./src/assets/temp/{player.id}_bingo.png"))
            except discord.Forbidden:
                await interaction.followup.send(
                    f"{player.mention} har ikke åpnet DM-ene sine :angry:\nSender den her i stedet",
                    file=discord.File(
                        f"./src/assets/temp/{player.id}_bingo.png", filename=f"SPOILER_{player.id}_bingo.png"
                    ),
                )
            finally:
                await asyncio.sleep(1)

    @discord.ui.button(label="Forlat", style=discord.ButtonStyle.gray)
    async def leave_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user == self.lobby["host"]:
            embed = embed_templates.error_warning(
                interaction, text="Du kan ikke forlate lobbyen som host. Slett lobbyen i stedet om ønskelig!"
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if interaction.user not in self.lobby["players"]:
            embed = embed_templates.error_warning(interaction, text="Du er ikke i lobbyen")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        self.lobby["players"].remove(interaction.user)
        await self.rerender_players(interaction)

        embed = embed_templates.success(interaction, text="Du har forlatt lobbyen")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Slett", style=discord.ButtonStyle.red)
    async def delete_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.lobby["host"]:
            embed = embed_templates.error_warning(interaction, text="Bare hosten kan slette lobbyen")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        self.lobby["ends"] = datetime.now()
        await interaction.message.delete()
        await interaction.response.send_message(
            embed=embed_templates.success(interaction, text="Lobbyen har blitt slettet")
        )


class KickSelectMenu(discord.ui.Select):
    def __init__(self, lobby: dict, parent_view: BingoView):
        self.lobby = lobby
        self.parent_view = parent_view
        options = [
            discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🔨", description=f"Kick {p.display_name}")
            for p in self.lobby["players"]
        ]
        super().__init__(placeholder="Kick en spiller", max_values=1, min_values=1, options=options)

    # TODO: DRY
    async def rerender_players(self, interaction: discord.Interaction):
        self.options = [
            discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🔨") for p in self.lobby["players"]
        ]
        embed = interaction.message.embeds[0].set_field_at(
            0, name="Spillere", value="\n".join([f"* {p.mention}" for p in self.lobby["players"]])
        )
        await interaction.message.edit(embed=embed, view=self.parent_view)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.lobby["host"]:
            embed = embed_templates.error_warning(interaction, text="Bare hosten kan kicke spillere")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if str(interaction.user.id) in interaction.data["values"][0]:
            embed = embed_templates.error_warning(interaction, text="Du kan ikke kicke deg selv")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        print(interaction.data["values"])
        self.lobby["kicked_players"].append(int(interaction.data["values"][0]))

        # Remove the player from the lobby
        # Since we only have the ID, we have to iterate through the list
        # unless we want to fetch the member object from the API
        # which we don't :)
        for i, member in enumerate(self.lobby["players"]):
            if member.id == int(interaction.data["values"][0]):
                self.lobby["players"].pop(i)
                break

        await self.rerender_players(interaction)
        await interaction.response.send_message(
            embed=embed_templates.success(interaction, text="Brukeren har blitt kicket fra lobbyen"), ephemeral=True
        )


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(CS2Bingo(bot))
