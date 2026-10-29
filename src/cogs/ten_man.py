"""
WARNING:
This code is an absolute hot steaming pile of garbage.
My excuse is just wanting things to work, for the most part, for now.
Below you will see a lot of stupid shit. Pls ignore
"""

import random
from datetime import timedelta
from typing import override

import discord
from discord import app_commands
from discord.ext import commands

from cogs.utils import embed_templates
from cogs.utils.discord_utils import Lobby
from cogs.utils.discord_utils import LobbyView

# Seconds without any interaction before the menus and buttons are disabled
SELECTION_TIMEOUT = 300


class TenMan(commands.Cog):
    """Join lobbies"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot
        self.active_lobbies = {}

    ten_man_group = app_commands.Group(name="10man", description="For planlegging og arrangering av 10 mans")

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 10)
    @ten_man_group.command(name="lag", description="Lag en 10 man lobby")
    async def lobby_create(self, interaction: discord.Interaction):
        """
        Create a 10 man lobby

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        if lobby := self.active_lobbies.get(str(interaction.user.id), None):
            if lobby.ends < discord.utils.utcnow():
                self.active_lobbies.pop(str(interaction.user.id))
            else:
                return await interaction.response.send_message(
                    embed=embed_templates.error_warning(
                        "Du hoster allerede en lobby",
                    )
                )

        for lobby in self.active_lobbies.values():
            if lobby.ends > discord.utils.utcnow() and any(p.id == interaction.user.id for p in lobby.players):
                return await interaction.response.send_message(
                    embed=embed_templates.error_warning(
                        "Du er allerede i en lobby",
                    )
                )

        self.active_lobbies[str(interaction.user.id)] = Lobby(
            host=interaction.user,
            players=[interaction.user],
            ends=discord.utils.utcnow() + timedelta(minutes=30),
            kicked_players=[],
        )

        time_left = discord.utils.format_dt(self.active_lobbies[str(interaction.user.id)].ends, "R")

        embed = discord.Embed(
            title="10 Man Lobby",
            description=f"Lobbyen stenger {time_left}. Bli med innen da!",
            color=interaction.user.color,
        )
        embed.set_author(name=interaction.user.global_name, icon_url=interaction.user.avatar)
        embed.add_field(name="Spillere", value=f"* {interaction.user.mention}", inline=False)
        view = TenManView(self.active_lobbies[str(interaction.user.id)], self.bot)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


class TenManView(LobbyView):
    def __init__(self, lobby: Lobby, bot: commands.Bot):
        super().__init__(lobby, bot)

    @discord.ui.button(label="Start", style=discord.ButtonStyle.green)
    @override
    async def start_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.lobby.host:
            embed = embed_templates.error_warning("Bare hosten kan starte")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        if len(self.lobby.players) < 3:
            embed = embed_templates.error_warning("Det må være mer enn 2 i lobbyen")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        await self.end_lobby()

        embed = interaction.message.embeds[0]
        embed.description = "Lobby startet! Dere skal nå velge lagledere"
        await interaction.message.edit(embed=embed, view=self)

        embed = discord.Embed(title="10 Man Lobby - Velg lagledere")
        view = TeamLeaderView(self.lobby, self.bot)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


# ------------------------------------------------------------------------------


class TeamLeaderView(discord.ui.View):
    def __init__(self, lobby: Lobby, bot: commands.Bot):
        super().__init__(timeout=SELECTION_TIMEOUT)
        self.lobby = lobby
        self.bot = bot
        self.message: discord.Message | None = None

        self.add_item(TeamLeaderSelectMenu(self))

    async def on_timeout(self):
        self.bot.logger.info("TeamLeaderView timed out")
        self.disable_interaction()
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass  # Deleted, or the interaction token used to edit it expired after 15 minutes

    def disable_interaction(self):
        self.bot.logger.info("TeamLeaderView disabled")
        for item in self.children:
            item.disabled = True

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        self.bot.logger.error("TeamLeaderView error", exc_info=error)
        embed = embed_templates.error_fatal("Oopsie woopsie, we made a fucky wucky!")
        await interaction.response.send_message(embed=embed, delete_after=10)


class TeamLeaderSelectMenu(discord.ui.Select):
    def __init__(self, parent_view: TeamLeaderView):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🧑‍🦲", description=p.global_name)
            for p in self.parent_view.lobby.players
        ]
        super().__init__(placeholder="Velg 2 lagledere", max_values=2, min_values=2, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.parent_view.lobby.host:
            embed = embed_templates.error_warning("Bare hosten kan velge lagledere")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        team_leaders = []
        for selected_player in interaction.data["values"]:
            for player in self.parent_view.lobby.players:
                if int(selected_player) == player.id:
                    team_leaders.append(player)
                    break

        self.parent_view.disable_interaction()
        embed = interaction.message.embeds[0]
        embed.description = "Lobbyledere har blitt valgt"
        embed.add_field(name="Lag 1", value=team_leaders[0].mention)
        embed.add_field(name="Lag 2", value=team_leaders[1].mention)
        await interaction.message.edit(embed=embed, view=self.parent_view)

        turn = random.randint(0, 1)
        embed = discord.Embed(title="10 Man Lobby - Velg spillere")
        embed.description = f"Det er {team_leaders[turn].mention} sin tur"
        embed.add_field(name="Lag 1", value=f"* {team_leaders[0].mention}", inline=False)
        embed.add_field(name="Lag 2", value=f"* {team_leaders[1].mention}", inline=False)
        view = TeamSelectView(self.parent_view.lobby, self.parent_view.bot, team_leaders, turn)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


# ------------------------------------------------------------------------------


class TeamSelectView(discord.ui.View):
    def __init__(self, lobby: Lobby, bot: commands.Bot, team_leaders: list[discord.User], turn: int):
        super().__init__(timeout=SELECTION_TIMEOUT)
        self.lobby = lobby
        self.bot = bot
        self.players = [p for p in self.lobby.players if p not in team_leaders]
        self.teams = [[team_leaders[0]], [team_leaders[1]]]
        self.turn = turn
        self.message: discord.Message | None = None

        self.add_item(TeamSelectMenu(self))

    async def on_timeout(self):
        self.bot.logger.info("TeamSelectView timed out")
        self.disable_interaction()
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass  # Deleted, or the interaction token used to edit it expired after 15 minutes

    def disable_interaction(self):
        self.bot.logger.info("TeamSelectView disabled")
        for item in self.children:
            item.disabled = True

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        self.bot.logger.error("TeamSelectView error", exc_info=error)
        embed = embed_templates.error_warning("Oopsie woopsie, we made a fucky wucky")
        await interaction.response.send_message(embed=embed, delete_after=10)

    def teams_ready(self, interaction):
        self.bot.logger.info("Teams ready!")
        embed = interaction.message.embeds[0]
        embed.title = "10 Man Lobby"
        embed.description = "Lagene er valgt!"
        self.add_item(MoveTeamVoiceButton(self))


class TeamSelectMenu(discord.ui.Select):
    def __init__(self, parent_view: TeamSelectView):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🤼‍♂️", description=p.global_name)
            for p in self.parent_view.players
        ]

        super().__init__(placeholder="Velg en spiller til laget ditt", max_values=1, min_values=1, options=options)

    async def rerender_players(self, interaction: discord.Interaction, turn_in_question: int):
        self.options = [
            discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🤼‍♂️", description=p.global_name)
            for p in self.parent_view.players
        ]

        embed = interaction.message.embeds[0]
        embed.set_field_at(
            turn_in_question,
            name=f"Lag {turn_in_question + 1}",
            value="\n".join([f"* {p.mention}" for p in self.parent_view.teams[turn_in_question]]),
        )
        if not self.options:
            self.parent_view.clear_items()
            self.parent_view.teams_ready(interaction)
        else:
            embed.description = f"Det er {self.parent_view.teams[self.parent_view.turn][0].mention} sin tur"

        await interaction.message.edit(embed=embed, view=self.parent_view)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.parent_view.teams[0][0] and interaction.user != self.parent_view.teams[1][0]:
            embed = embed_templates.error_warning("Bare lagledere kan velge spillere")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        if interaction.user != self.parent_view.teams[self.parent_view.turn][0]:
            embed = embed_templates.error_warning("Det er ikke din tur enda")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        turn_in_question = self.parent_view.turn
        self.parent_view.turn = 0 if self.parent_view.turn == 1 else 1

        for i, player in enumerate(self.parent_view.players):
            if player.id == int(interaction.data["values"][0]):
                self.parent_view.players.pop(i)
                self.parent_view.teams[turn_in_question].append(player)
                break

        await self.rerender_players(interaction, turn_in_question)

        embed = embed_templates.success("Bruker valgt!")
        await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=5)


# ------------------------------------------------------------------------------


class MoveTeamVoiceButton(discord.ui.Button):
    def __init__(self, parent_view: TeamSelectView):
        self.parent_view = parent_view
        self.clicked = {"1": None, "2": None}
        super().__init__(style=discord.ButtonStyle.primary, label="Opprett kanal og flytt lag", emoji="🔊")

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.parent_view.teams[0][0] and interaction.user != self.parent_view.teams[1][0]:
            embed = embed_templates.error_warning("Bare lagleder kan flytte laget!")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        if interaction.user == self.parent_view.teams[0][0]:
            team = {"number": "1", "players": self.parent_view.teams[0]}
        else:
            team = {"number": "2", "players": self.parent_view.teams[1]}

        # Reuse tempvoice logic from cog
        if not (tempvoice_cog := self.parent_view.bot.get_cog("TempVoice")):
            embed = embed_templates.error_fatal("Tempvoice er ikke tilgjengelig akkurat nå")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)
        temp_voice = tempvoice_cog.temp_voice_helper

        if not self.clicked[team["number"]]:
            channel = await temp_voice.create_temp_voice(interaction, name=f"10 man - Lag {team['number']}")
            if not channel:
                return
            self.clicked[team["number"]] = channel
            failed_users = await temp_voice.move_players(interaction, self.clicked[team["number"]], team["players"])
        else:
            embed = embed_templates.error_warning(
                f"Kanal for lag {team['number']} allerede opprettet og spillere flyttet!"
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        if failed_users:
            failed_users = "\n".join([f"* {user.mention}" for user in failed_users])
            embed = embed_templates.error_warning(
                f"Klarte ikke å flytte følgende brukere til kanalen:\n{failed_users}\n\n"
                + "Dette kan være fordi brukere(ne) ikke er koblet til en kanal fra før "
                + "eller at jeg ikke har tillatelse til å flytte",
            )
            return await interaction.response.send_message(embed=embed, delete_after=10)

        embed = embed_templates.success(f"Flyttet lag {team['number']} til voice!")
        await interaction.response.send_message(embed=embed, delete_after=10)


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(TenMan(bot))
