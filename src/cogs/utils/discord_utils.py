import os
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

import discord
from discord.ext import commands
from discord.ext import tasks

from . import embed_templates
from .misc_utils import Paginator


async def send_as_txt_file(interaction: discord.Interaction, content: str, file_path: str):
    """
    Sends a string as a txt file and deletes the file afterwards

    Parameters
    ----------
    interaction (discord.Interaction): Slash command context object
    content (str): String that's too long to send
    file_path (str): Path to file
    """

    # Create file
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(content)

    # Send file
    txt_file = discord.File(file_path)
    await interaction.response.send_message(file=txt_file)

    # Delete file
    try:
        os.remove(file_path)
    except OSError:
        pass


async def get_file_bytesio(file: discord.Attachment | discord.Asset) -> BytesIO:
    """
    Returns a BytesIO object of the file

    Parameters
    -----------
    file (discord.Attatchment | discord.Asset): The file to get the BytesIO object of

    Returns
    -----------
    (BytesIO): The file as a BytesIO object
    """

    input = BytesIO()
    input.write(await file.read())
    input.seek(0)
    return input


class ScrollerButton(discord.ui.Button):
    """Button that scrolls through pages in a scroller view"""

    def __init__(
        self,
        paginator: Paginator,
        button_action: callable,
        content_constructor: callable,
        owner: discord.User | discord.Member,
        label: str,
        disabled: bool = False,
    ):
        """
        Parameters
        -----------
        paginator (Paginator): The paginator object that contains the data to be paginated
        button_action (callable): The function that returns the requested page
        content_constructor (callable): A function that takes a paginator object and a page number and returns an embed
        owner (discord.User|discord.Member): The user that invoked the paginator. Only this user can use the button
        """

        super().__init__(label=label, disabled=disabled)
        self.paginator = paginator
        self.button_action = button_action
        self.content_constructor = content_constructor
        self.owner = owner

    async def callback(self, interaction: discord.Interaction):
        """
        What to do when the button is pressed

        Parameters
        -----------
        interaction (discord.Interaction): Slash command context object
        """

        if interaction.user.id != self.owner.id:
            return await interaction.response.send_message(
                "Bare den som skrev kommandoen kan bruke denne knappen", ephemeral=True
            )

        await interaction.response.defer()

        content = self.content_constructor(self.button_action(), interaction.message.embeds[0])
        await interaction.message.edit(
            embed=content, view=Scroller(self.paginator, self.owner, self.content_constructor)
        )


class Scroller(discord.ui.View):
    """View that allows scrolling through pages of data using the pagination module"""

    def __init__(
        self, paginatior: Paginator, owner: discord.User | discord.Member, content_constructor: callable = None
    ):
        """
        Parameters
        -----------
        paginator (Paginator): The paginator object that contains the data to be paginated
        owner (discord.User|discord.Member): The user that invoked the paginator. Only this user can use the buttons
        content_constructor (callable): A function that takes a paginator object and a page number and returns an embed
        """

        super().__init__()
        self.paginator = paginatior
        self.content_constructor = content_constructor if content_constructor else self.__default_content_constructor

        self.add_item(
            ScrollerButton(
                self.paginator,
                self.paginator.first_page,
                self.content_constructor,
                owner,
                label="<<",
                disabled=self.paginator.current_page == 1,
            )
        )
        self.add_item(
            ScrollerButton(
                self.paginator,
                self.paginator.previous_page,
                self.content_constructor,
                owner,
                label="<",
                disabled=self.paginator.current_page == 1,
            )
        )
        self.add_item(
            ScrollerButton(
                self.paginator,
                self.paginator.next_page,
                self.content_constructor,
                owner,
                label=">",
                disabled=self.paginator.current_page == self.paginator.total_page_count,
            )
        )
        self.add_item(
            ScrollerButton(
                self.paginator,
                self.paginator.last_page,
                self.content_constructor,
                owner,
                label=">>",
                disabled=self.paginator.current_page == self.paginator.total_page_count,
            )
        )

    def construct_embed(self, base_embed: discord.Embed):
        """
        Constructs the embed to be displayed

        Parameters
        -----------
        base_embed (discord.Embed): The base embed to add fields to
        """

        return self.content_constructor(self.paginator.get_current_page(), embed=base_embed)

    def __default_content_constructor(self, page: list, embed: discord.Embed) -> discord.Embed:
        """
        Default embed template for the paginator

        Parameters
        ----------
        paginator (Paginator): Paginator dataclass
        page (list): List of streaks to display on a page
        embed (discord.Embed): Embed to add fields to
        """

        embed.description = "\n".join(page)
        embed.set_footer(text=f"Side {self.paginator.current_page}/{self.paginator.total_page_count}")
        return embed


@dataclass
class Lobby:
    host: discord.User
    players: list[discord.User]
    ends: datetime
    kicked_players: list[discord.User]


class LobbyView(discord.ui.View):
    def __init__(self, lobby: Lobby, bot: commands.Bot):
        lobby_end = (lobby.ends - datetime.now()).total_seconds()
        super().__init__(timeout=lobby_end)

        self.lobby = lobby
        self.bot = bot

        self.add_item(_KickSelectMenu(self))

    async def on_timeout(self):
        await self.end_lobby()

    async def end_lobby(self):
        self.lobby.ends = datetime.now()
        for item in self.children:
            item.disabled = True

    async def rerender_players(self, interaction: discord.Interaction):
        self.children[-1].options = [
            discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🔨") for p in self.lobby.players
        ]
        embed = interaction.message.embeds[0].set_field_at(
            0,
            name=f"Spillere ({len(self.lobby.players)})",
            value="\n".join([f"* {p.mention}" for p in self.lobby.players]),
        )
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Bli med", style=discord.ButtonStyle.blurple)
    async def join_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
        if datetime.now() > self.lobby.ends:
            embed = embed_templates.error_warning("Lobbyen har allerede startet")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        if (
            interaction.user.id in self.lobby.kicked_players
        ):  # We have to use the ID here to avoid fetching the member object in the selection menu
            embed = embed_templates.error_warning("Du er blitt kastet ut av lobbyen")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        if interaction.user in self.lobby.players:
            embed = embed_templates.error_warning("Du er allerede i lobbyen")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        if len(self.lobby.players) >= 10:
            embed = embed_templates.error_warning("Lobbyen er full")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        self.lobby.players.append(interaction.user)
        await self.rerender_players(interaction)

        embed = embed_templates.success("Du har blitt med i lobbyen")
        await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=5)

    @discord.ui.button(label="Start", style=discord.ButtonStyle.green)
    async def start_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.lobby.host:
            embed = embed_templates.error_warning("Bare hosten kan starte")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        if len(self.lobby.players) < 3:
            embed = embed_templates.error_warning("Det må være mer enn 2 i lobbyen")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        await self.end_lobby()

        embed = interaction.message.embeds[0]
        embed.description = "Lobbyen har startet!"
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Forlat", style=discord.ButtonStyle.gray)
    async def leave_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user == self.lobby.host:
            embed = embed_templates.error_warning(
                "Du kan ikke forlate lobbyen som host. Slett lobbyen i stedet om ønskelig!"
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        if interaction.user not in self.lobby.players:
            embed = embed_templates.error_warning("Du er ikke i lobbyen")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        self.lobby.players.remove(interaction.user)
        await self.rerender_players(interaction)

        embed = embed_templates.success("Du har forlatt lobbyen")
        await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=5)

    @discord.ui.button(label="Slett", style=discord.ButtonStyle.red)
    async def delete_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.lobby.host:
            embed = embed_templates.error_warning("Bare hosten kan slette lobbyen")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        self.lobby.ends = datetime.now()
        await interaction.message.delete()

        embed = embed_templates.success("Lobbyen har blitt slettet")
        await interaction.response.send_message(embed=embed, delete_after=5)


class _KickSelectMenu(discord.ui.Select):
    def __init__(self, parent_view: LobbyView):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🔨", description=f"Kick {p.display_name}")
            for p in self.parent_view.lobby.players
        ]
        super().__init__(placeholder="Kick en spiller", max_values=1, min_values=1, options=options)

    # TODO: DRY
    async def rerender_players(self, interaction: discord.Interaction):
        self.options = [
            discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🔨")
            for p in self.parent_view.lobby.players
        ]
        embed = interaction.message.embeds[0].set_field_at(
            0, name="Spillere", value="\n".join([f"* {p.mention}" for p in self.parent_view.lobby.players])
        )
        await interaction.message.edit(embed=embed, view=self.parent_view)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.parent_view.lobby.host:
            embed = embed_templates.error_warning("Bare hosten kan kicke spillere")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        if str(interaction.user.id) in interaction.data["values"][0]:
            embed = embed_templates.error_warning("Du kan ikke kicke deg selv")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        self.parent_view.lobby.kicked_players.append(int(interaction.data["values"][0]))

        # Remove the player from the lobby
        # Since we only have the ID, we have to iterate through the list
        # unless we want to fetch the member object from the API
        # which we don't :)
        for i, member in enumerate(self.parent_view.lobby.players):
            if member.id == int(interaction.data["values"][0]):
                self.parent_view.lobby.players.pop(i)
                break

        await self.rerender_players(interaction)

        embed = embed_templates.success("Brukeren har blitt sparket fra lobbyen")
        await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=5)


class TempVoiceHelper:
    """Allows users to create a temporary channel that will be deleted after 5 minutes of inactivity"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot
        self.temp_vc_channels = {}
        self.check_temp_vc_channels.start()

    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        """
        Listen for disconnects from the temporary voice channels
        """

        for channel in (before.channel, after.channel):
            if channel not in self.temp_vc_channels:
                continue

            if len(channel.members) == 0:
                self.temp_vc_channels[channel]["no_members_since"] = datetime.now()
                self.bot.logger.info(f"Temporary voice channel {channel} has no members. Will be deleted in 1 minutes")
            else:
                self.temp_vc_channels[channel]["no_members_since"] = None

    @tasks.loop(minutes=1)
    async def check_temp_vc_channels(self):
        """
        Check for temporary voice channels that have been inactive for 1 minute
        """

        for channel, data in self.temp_vc_channels.copy().items():
            if not data["no_members_since"]:
                continue

            if (datetime.now() - data["no_members_since"]).total_seconds() >= 60:
                try:
                    await channel.delete(reason="tempvoice kanal inaktiv i 1 minutt")
                except discord.Forbidden:
                    self.bot.logger.info(f"Failed to delete temporary voice channel {channel}")
                else:
                    self.bot.logger.info(f"Deleted temporary voice channel {channel}")
                finally:
                    del self.temp_vc_channels[channel]

    async def create_temp_voice(
        self, interaction: discord.Interaction, name: str, limit: int = 0
    ) -> discord.VoiceChannel | None:
        """
        Create a temporary voice channel

        Parameters
        ----------
        interaction (discord.Interaction): The interaction object
        name (str): The name of the channel
        limit (int): The user limit of the channel

        Returns
        ----------
        (discord.VoiceChannel) | None: The object for the newly created channel. None if failed
        """

        # Get the UiO Gaming server's VC category. If the command is not invoked in that server it should still be fine
        # since the it will return None if not found.
        vc_category = interaction.guild.get_channel(747542544291987601)

        try:
            channel = await interaction.guild.create_voice_channel(
                name=name,
                user_limit=limit,
                category=vc_category,
                reason=f"tempvoice kommando av {interaction.user.name}",
            )
        except discord.Forbidden:
            self.bot.logger.error(f"Failed to create temporary voice channel in {interaction.guild}")
            await interaction.response.send_message(
                embed=embed_templates.error_fatal("Jeg har ikke tilgang til å opprette en talekanal")
            )
            return

        self.bot.logger.info(f"Created temporary voice channel {channel} in {interaction.guild}")

        self.temp_vc_channels[channel] = {"created": datetime.now(), "no_members_since": None}

        try:
            await interaction.user.move_to(channel)
        except discord.Forbidden:
            self.bot.logger.info(
                f"Failed to move {interaction.user} to temporary voice channel {channel}. Missing permissions"
            )
        except discord.HTTPException:
            self.bot.logger.info(
                f"Failed to move {interaction.user} to temporary voice channel {channel}. User not connected to voice"
            )

        return channel

    async def move_players(
        self, interaction: discord.Interaction, channel: discord.VoiceChannel, users: list[discord.User]
    ) -> list[discord.User] | None:
        """
        Atteampts to move a list of users to a desired voice channel


        Parameters
        ----------
        interaction (discord.Interaction): The interaction object
        channel (discord.VoiceChannel): The channel the users should be moved to
        users (list[discord.User]): A list of users to be moved

        Returns
        ----------
        (list[discord.User]) | None: A list of users that failed to be moved. None if all users were moved
        """

        failed_users = []

        for user in users:
            try:
                await user.move_to(channel)
            except discord.Forbidden:
                self.bot.logger.info(f"Failed to move {user} to temporary voice channel {channel}. Missing permissions")
                failed_users.append(user)
            except discord.HTTPException:
                self.bot.logger.info(
                    f"Failed to move {user} to temporary voice channel {channel}. User not connected to voice"
                )
                failed_users.append(user)

        return failed_users
