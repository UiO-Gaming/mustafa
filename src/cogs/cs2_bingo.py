import asyncio
import json
import random
from datetime import datetime
from datetime import timedelta
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


class CS2Bingo(commands.Cog):
    """Join lobbies and generate bingo sheets for CS2"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot
        self.active_lobbies = {}  # dict[str, discord_utils.Lobby]

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
            if lobby.ends < datetime.now():
                self.active_lobbies.pop(str(interaction.user.id))
            else:
                return await interaction.response.send_message(
                    embed=embed_templates.error_warning("Du hoster allerede en lobby")
                )

        for lobby in self.active_lobbies.values():
            if lobby.ends > datetime.now() and any(p.id == interaction.user.id for p in lobby.players):
                return await interaction.response.send_message(
                    embed=embed_templates.error_warning("Du er allerede i en lobby")
                )

        self.active_lobbies[str(interaction.user.id)] = Lobby(
            host=interaction.user,
            players=[interaction.user],
            ends=datetime.now() + timedelta(minutes=10),
            kicked_players=[],
        )

        time_left = discord.utils.format_dt(self.active_lobbies[str(interaction.user.id)].ends, "R")

        embed = discord.Embed(
            title="Bingolobby",
            description=f"Lobbyen stenger {time_left}. Bli med innen da!",
            color=interaction.user.color,
        )
        embed.set_author(name=interaction.user.global_name, icon_url=interaction.user.avatar)
        embed.add_field(name="Spillere", value=f"* {interaction.user.mention}", inline=False)
        view = BingoView(self.active_lobbies[str(interaction.user.id)], self.bot)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


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
        assert 0 < len(players) <= 10

        default_space = cls.CELLS["all"]

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
    async def generate_sheets(cls, players: list[discord.Member], bot: commands.Bot):
        """
        Generate bingo sheets for each player

        Parameters
        ----------
        players (list[str]): List of the player's discord IDs as strings
        """

        players = [str(p.id) for p in players]

        sample_space = await cls.sample_cells(players, bot)
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
                await misc_utils.put_text_in_box(
                    sliced,
                    sample_space.pop(),
                    top_left=(i * width + 1, j * width + 1),
                    bottom_right=((i + 1) * width, (j + 1) * width),
                    font_path=cls.FONT_PATH,
                )

        return image


class BingoView(LobbyView):
    def __init__(self, lobby: Lobby, bot: commands.Bot):
        super().__init__(lobby, bot)

    @discord.ui.button(label="Start", style=discord.ButtonStyle.green)
    @override
    async def start_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
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

        await BingoGenerator.generate_sheets(self.lobby.players, self.bot)
        for player in self.lobby.players:
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


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(CS2Bingo(bot))
