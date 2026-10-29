import asyncio
import json
import random
from datetime import timedelta
from io import BytesIO
from typing import override

import cv2
import discord
import numpy as np
from discord import app_commands
from discord.ext import commands

from cogs.utils import embed_templates
from cogs.utils import misc_utils
from cogs.utils.discord_utils import Lobby
from cogs.utils.discord_utils import LobbyView
from cogs.utils.discord_utils import open_lobby


class CS2Bingo(commands.Cog):
    """Join lobbies and generate bingo sheets for CS2"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot
        self.active_lobbies: dict[int, Lobby] = {}

    bingo_group = app_commands.Group(name="cs2bingo", description="Bingo commands for CS2")

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 10)
    @bingo_group.command(name="lag", description="Lag en bingolobby")
    async def bingo_create(self, interaction: discord.Interaction):
        """
        Create a bingo lobby

        Parameters
        ----------
        interaction (discord.Interaction): The slash command interaction
        """

        await open_lobby(interaction, self.active_lobbies, BingoView, "Bingolobby", timedelta(minutes=10))


class BingoGenerator:
    """
    Generate bingo sheets for CS2
    """

    FONT_PATH = "./src/assets/fonts/comic.ttf"
    BINGO_PATH = "./src/assets/cs2_bingo"

    with open(f"{BINGO_PATH}/cells.json") as f:
        CELLS = json.load(f)

    with open(f"{BINGO_PATH}/names.json") as f:
        NAMES = json.load(f)

    @classmethod
    async def sample_cells(cls, players: list[str], bot: commands.Bot) -> dict[str, list[str]]:
        """
        Pick 25 squares for each player's sheet

        Parameters
        ----------
        players (list[str]): The Discord IDs of the players
        bot (commands.Bot): The bot instance

        Returns
        ----------
        (dict[str, list[str]]): Each player's squares, keyed by their Discord ID
        """

        assert 0 < len(players) <= 10

        default_space = list(cls.CELLS["all"])

        if len(players) < 5:
            default_space += cls.CELLS["randoms"]

        player_cells = {}

        for player in players:
            other_players = players.copy()
            other_players.remove(player)
            player_space = default_space + [i for op in other_players for i in cls.CELLS.get(op, [])]
            other_players.append("du")

            other_players_names = [
                cls.NAMES.get(op, bot.get_user(int(op)).display_name) if op != "du" else op for op in other_players
            ]
            player_space += [s.format(random.choice(other_players_names)) for s in cls.CELLS["parameterized"]]

            sampled_cells = np.random.choice(player_space, replace=False, size=25)
            player_cells[player] = list(sampled_cells)

        return player_cells

    @classmethod
    async def generate_sheets(cls, players: list[discord.Member], bot: commands.Bot) -> dict[str, bytes]:
        """
        Generate bingo sheets for each player

        Parameters
        ----------
        players (list[discord.Member]): The players to generate sheets for
        bot (commands.Bot): The bot instance

        Returns
        ----------
        (dict[str, bytes]): Each player's sheet as PNG data, keyed by their discord ID as a string
        """

        players = [str(p.id) for p in players]

        sample_space = await cls.sample_cells(players, bot)
        assert len(sample_space) == len(players)
        image = cv2.imread(f"{cls.BINGO_PATH}/cs2_bingo_sheet.png")

        player_sheets = {}

        for player in players:
            player_sheets[player] = await asyncio.to_thread(cls.generate_sheet, sample_space[player], image)

        return player_sheets

    @classmethod
    def generate_sheet(cls, sample_space: list, image: np.ndarray) -> bytes:
        """
        Draw the squares on a bingo sheet

        Parameters
        ----------
        sample_space (list): The squares to draw. Emptied as they are drawn
        image (np.ndarray): The empty bingo sheet

        Returns
        ----------
        (bytes): The sheet as PNG data
        """

        image = image.copy()

        # start = 8, 294
        # end = 625, 910

        sliced = image[295:910, 10:625]
        # patches = []

        for i in range(0, 5):
            for j in range(0, 5):
                width = 123
                misc_utils.put_text_in_box(
                    sliced,
                    sample_space.pop(),
                    top_left=(i * width + 1, j * width + 1),
                    bottom_right=((i + 1) * width, (j + 1) * width),
                    font_path=cls.FONT_PATH,
                )

        return cv2.imencode(".png", image)[1].tobytes()


class BingoView(LobbyView):
    """Bingo lobby that sends every player a bingo sheet when started"""

    def __init__(self, lobby: Lobby, bot: commands.Bot):
        """
        Parameters
        ----------
        lobby (Lobby): The lobby to show
        bot (commands.Bot): The bot instance
        """

        super().__init__(lobby, bot)

    @discord.ui.button(label="Start", style=discord.ButtonStyle.green)
    @override
    async def start_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Close the lobby and send every player their bingo sheet

        Parameters
        ----------
        interaction (discord.Interaction): The interaction that triggered this
        button (discord.ui.Button): The button that was pressed
        """

        if interaction.user != self.lobby.host:
            embed = embed_templates.error_warning("Bare hosten kan starte bingoen")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        await self.end_lobby()

        embed = interaction.message.embeds[0]
        embed.description = "Bingoen har startet!"
        await interaction.message.edit(embed=embed, view=self)

        mention_players = " ".join([f"{p.mention}" for p in self.lobby.players])
        embed = embed_templates.success(
            "Bingoen har startet\n\nDere vil nå få tilsendt bingobrettene deres på DM. "
            + "Sørg for at jeg kan slide inn i dem :smirk:",
        )
        await interaction.response.send_message(content=mention_players, embed=embed)

        sheets = await BingoGenerator.generate_sheets(self.lobby.players, self.bot)
        for player in self.lobby.players:
            sheet = sheets[str(player.id)]
            try:
                await player.send(file=discord.File(BytesIO(sheet), filename=f"{player.id}_bingo.png"))
            except discord.Forbidden:
                await interaction.followup.send(
                    f"{player.mention} har ikke åpnet DM-ene sine :angry:\nSender den her i stedet",
                    file=discord.File(BytesIO(sheet), filename=f"SPOILER_{player.id}_bingo.png"),
                )
            finally:
                await asyncio.sleep(1)


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): The bot instance
    """

    await bot.add_cog(CS2Bingo(bot))
