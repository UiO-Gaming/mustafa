"""
10 man lobbies. The host opens a lobby and picks two team leaders, who take turns picking players for their teams.
Every step happens in the lobby message, which is edited as the flow goes on
"""

import random
from datetime import timedelta
from typing import override

import discord
from discord import app_commands
from discord.ext import commands

from cogs.utils import discord_utils
from cogs.utils import embed_templates

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
        self.active_lobbies: dict[int, discord_utils.Lobby] = {}

    ten_man_group = app_commands.Group(name="10man", description="For planlegging og arrangering av 10 mans")

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 10)
    @ten_man_group.command(name="lag", description="Lag en 10 man lobby")
    async def lobby_create(self, interaction: discord.Interaction):
        """
        Create a 10 man lobby

        Parameters
        ----------
        interaction (discord.Interaction): The slash command interaction
        """

        await discord_utils.open_lobby(
            interaction, self.active_lobbies, TenManView, "10 Man Lobby", timedelta(minutes=30)
        )


class TenManView(discord_utils.LobbyView):
    """The lobby players join before the teams are picked"""

    @discord.ui.button(label="Start", style=discord.ButtonStyle.green)
    @override
    async def start_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Close the lobby and let the host pick team leaders

        Parameters
        ----------
        interaction (discord.Interaction): The interaction that triggered this
        button (discord.ui.Button): The button that was pressed
        """

        if interaction.user != self.lobby.host:
            embed = embed_templates.error_warning("Bare hosten kan starte")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        if len(self.lobby.players) < 3:
            embed = embed_templates.error_warning("Det må være mer enn 2 i lobbyen")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        await self.end_lobby()

        view = TeamLeaderView(self.lobby, self.bot, self.message)
        await interaction.response.edit_message(embed=view.embed(), view=view)


class TeamDraft:
    """Two team leaders taking turns picking players for their teams"""

    def __init__(self, leaders: list[discord.Member], players: list[discord.Member]):
        """
        Parameters
        ----------
        leaders (list[discord.Member]): The two team leaders
        players (list[discord.Member]): The players to pick from
        """

        self.teams = [[leaders[0]], [leaders[1]]]
        self.remaining = players
        self.turn = random.randint(0, 1)

    @property
    def leaders(self) -> list[discord.Member]:
        """
        Returns
        ----------
        (list[discord.Member]): The two team leaders
        """

        return [team[0] for team in self.teams]

    @property
    def done(self) -> bool:
        """
        Returns
        ----------
        (bool): Whether every player has been picked
        """

        return not self.remaining

    def pick(self, player_id: int):
        """
        Move a player to the team whose turn it is, and give the turn to the other team

        Parameters
        ----------
        player_id (int): The Discord ID of the picked player
        """

        player = next(player for player in self.remaining if player.id == player_id)
        self.remaining.remove(player)
        self.teams[self.turn].append(player)
        self.turn = 1 - self.turn

    def embed(self) -> discord.Embed:
        """
        Returns
        ----------
        (discord.Embed): The teams so far, and whose turn it is
        """

        if self.done:
            embed = discord.Embed(title="10 Man - Lagene er klare", description="Lagene er valgt!")
        else:
            embed = discord.Embed(
                title="10 Man - Velg spillere", description=f"Det er {self.leaders[self.turn].mention} sin tur"
            )

        for i, team in enumerate(self.teams):
            embed.add_field(
                name=f"Lag {i + 1}", value="\n".join(f"* {player.mention}" for player in team), inline=False
            )

        return embed


class StageView(discord.ui.View):
    """A step of the flow after the lobby has closed"""

    def __init__(self, lobby: discord_utils.Lobby, bot: commands.Bot, message: discord.PartialMessage):
        """
        Parameters
        ----------
        lobby (Lobby): The closed lobby
        bot (commands.Bot): The bot instance
        message (discord.PartialMessage): The lobby message, edited with the bot's own token on timeout
        """

        super().__init__(timeout=SELECTION_TIMEOUT)
        self.lobby = lobby
        self.bot = bot
        self.message = message

    async def deny(self, interaction: discord.Interaction, reason: str) -> bool:
        """
        Tell the user why they can't use this step

        Parameters
        ----------
        interaction (discord.Interaction): The interaction that triggered this
        reason (str): Why the user was denied

        Returns
        ----------
        (bool): Always False, so it can be returned from interaction_check
        """

        embed = embed_templates.error_warning(reason)
        await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)
        return False

    async def on_timeout(self):
        """
        Disable the step's menus and buttons after SELECTION_TIMEOUT seconds without interaction
        """

        for item in self.children:
            item.disabled = True

        try:
            await self.message.edit(view=self)
        except discord.HTTPException:
            pass  # The message has been deleted

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        """
        Log the error and tell the user something went wrong

        Parameters
        ----------
        interaction (discord.Interaction): The interaction that triggered this
        error (Exception): The error that was raised
        item (discord.ui.Item): The menu or button that was used
        """

        self.bot.logger.error(f"{type(self).__name__} error", exc_info=error)

        embed = embed_templates.error_fatal("Oopsie woopsie, we made a fucky wucky!")
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)


class TeamLeaderView(StageView):
    """The host picks two team leaders"""

    def __init__(self, lobby: discord_utils.Lobby, bot: commands.Bot, message: discord.PartialMessage):
        """
        Parameters
        ----------
        lobby (Lobby): The closed lobby
        bot (commands.Bot): The bot instance
        message (discord.PartialMessage): The lobby message
        """

        super().__init__(lobby, bot, message)
        self.add_item(TeamLeaderSelect(lobby.players))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        Only let the host pick team leaders

        Parameters
        ----------
        interaction (discord.Interaction): The interaction that triggered this

        Returns
        ----------
        (bool): Whether the user may use the menu
        """

        if interaction.user != self.lobby.host:
            return await self.deny(interaction, "Bare hosten kan velge lagledere")
        return True

    def embed(self) -> discord.Embed:
        """
        Returns
        ----------
        (discord.Embed): The players to pick team leaders from
        """

        embed = discord.Embed(
            title="10 Man - Velg lagledere", description=f"{self.lobby.host.mention} velger lagledere"
        )
        embed.add_field(
            name=f"Spillere ({len(self.lobby.players)})",
            value="\n".join(f"* {player.mention}" for player in self.lobby.players),
        )
        return embed


class TeamLeaderSelect(discord.ui.Select):
    """Menu for picking the two team leaders"""

    def __init__(self, players: list[discord.Member]):
        """
        Parameters
        ----------
        players (list[discord.Member]): The players to pick team leaders from
        """

        options = [
            discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🧑‍🦲", description=p.global_name)
            for p in players
        ]
        super().__init__(placeholder="Velg 2 lagledere", min_values=2, max_values=2, options=options)

    async def callback(self, interaction: discord.Interaction):
        """
        Start the draft with the picked team leaders

        Parameters
        ----------
        interaction (discord.Interaction): The interaction that triggered this
        """

        view: TeamLeaderView = self.view
        leaders = [player for player in view.lobby.players if str(player.id) in self.values]
        others = [player for player in view.lobby.players if player not in leaders]
        draft = TeamDraft(leaders, others)

        view.stop()
        await interaction.response.edit_message(embed=draft.embed(), view=DraftView(view, draft))


class DraftView(StageView):
    """The team leaders take turns picking players"""

    def __init__(self, previous: StageView, draft: TeamDraft):
        """
        Parameters
        ----------
        previous (StageView): The step before this one
        draft (TeamDraft): The draft so far
        """

        super().__init__(previous.lobby, previous.bot, previous.message)
        self.draft = draft
        self.add_item(PlayerSelect(draft.remaining))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        Only let the team leader whose turn it is pick

        Parameters
        ----------
        interaction (discord.Interaction): The interaction that triggered this

        Returns
        ----------
        (bool): Whether the user may use the menu
        """

        if interaction.user not in self.draft.leaders:
            return await self.deny(interaction, "Bare lagledere kan velge spillere")
        if interaction.user != self.draft.leaders[self.draft.turn]:
            return await self.deny(interaction, "Det er ikke din tur enda")
        return True


class PlayerSelect(discord.ui.Select):
    """Menu for picking the next player for a team"""

    def __init__(self, players: list[discord.Member]):
        """
        Parameters
        ----------
        players (list[discord.Member]): The players that haven't been picked yet
        """

        options = [
            discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🤼‍♂️", description=p.global_name)
            for p in players
        ]
        super().__init__(placeholder="Velg en spiller til laget ditt", options=options)

    async def callback(self, interaction: discord.Interaction):
        """
        Add the picked player to the team, and move on to voice once everyone is picked

        Parameters
        ----------
        interaction (discord.Interaction): The interaction that triggered this
        """

        view: DraftView = self.view
        view.draft.pick(int(self.values[0]))

        next_view = VoiceView(view, view.draft.teams) if view.draft.done else DraftView(view, view.draft)
        view.stop()
        await interaction.response.edit_message(embed=view.draft.embed(), view=next_view)


class VoiceView(StageView):
    """Each team leader can create a voice channel for their team and move the team there"""

    def __init__(self, previous: StageView, teams: list[list[discord.Member]]):
        """
        Parameters
        ----------
        previous (StageView): The step before this one
        teams (list[list[discord.Member]]): The teams. The first player of each team is its leader
        """

        super().__init__(previous.lobby, previous.bot, previous.message)
        self.teams = teams
        self.moved_teams: set[int] = set()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        Only let team leaders move their team

        Parameters
        ----------
        interaction (discord.Interaction): The interaction that triggered this

        Returns
        ----------
        (bool): Whether the user may use the button
        """

        if interaction.user not in (self.teams[0][0], self.teams[1][0]):
            return await self.deny(interaction, "Bare lagleder kan flytte laget!")
        return True

    @discord.ui.button(label="Opprett kanal og flytt lag", emoji="🔊", style=discord.ButtonStyle.primary)
    async def move_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Create a temporary voice channel for the leader's team and move the team there

        Parameters
        ----------
        interaction (discord.Interaction): The interaction that triggered this
        button (discord.ui.Button): The button that was pressed
        """

        team = 0 if interaction.user == self.teams[0][0] else 1
        if team in self.moved_teams:
            embed = embed_templates.error_warning(f"Kanal for lag {team + 1} allerede opprettet og spillere flyttet!")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        if not (tempvoice_cog := self.bot.get_cog("TempVoice")):
            embed = embed_templates.error_fatal("Tempvoice er ikke tilgjengelig akkurat nå")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)
        temp_voice = tempvoice_cog.temp_voice_helper

        # Mark the team before awaiting, so pressing twice quickly doesn't create two channels
        self.moved_teams.add(team)
        if not (channel := await temp_voice.create_temp_voice(interaction, name=f"10 man - Lag {team + 1}")):
            self.moved_teams.discard(team)
            return  # create_temp_voice has already told the user what went wrong

        if failed_users := await temp_voice.move_players(interaction, channel, self.teams[team]):
            failed_users = "\n".join(f"* {user.mention}" for user in failed_users)
            embed = embed_templates.error_warning(
                f"Klarte ikke å flytte følgende brukere til kanalen:\n{failed_users}\n\n"
                + "Dette kan være fordi brukere(ne) ikke er koblet til en kanal fra før "
                + "eller at jeg ikke har tillatelse til å flytte",
            )
            return await interaction.response.send_message(embed=embed, delete_after=10)

        embed = embed_templates.success(f"Flyttet lag {team + 1} til voice!")
        await interaction.response.send_message(embed=embed, delete_after=10)


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): The bot instance
    """

    await bot.add_cog(TenMan(bot))
