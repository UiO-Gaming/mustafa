from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timedelta
from io import BytesIO

import discord
import psycopg
from discord.ext import commands
from discord.ext import tasks

from . import embed_templates
from .misc_utils import Paginator
from .misc_utils import log_errors


async def send_as_txt_file(interaction: discord.Interaction, content: str, filename: str):
    """
    Sends a string as a txt file

    Parameters
    ----------
    interaction (discord.Interaction): The interaction that triggered this
    content (str): String that's too long to send
    filename (str): Name of the file as shown in Discord
    """

    txt_file = discord.File(BytesIO(content.encode("utf-8")), filename=filename)
    await interaction.response.send_message(file=txt_file)


async def get_file_bytesio(file: discord.Attachment | discord.Asset) -> BytesIO:
    """
    Returns a BytesIO object of the file

    Parameters
    ----------
    file (discord.Attachment | discord.Asset): The file to get the BytesIO object of

    Returns
    ----------
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
        ----------
        paginator (Paginator): The paginator object that contains the data to be paginated
        button_action (callable): The function that returns the requested page
        content_constructor (callable): A function that takes a paginator object and a page number and returns an embed
        owner (discord.User | discord.Member): The user that invoked the paginator. Only this user can use the button
        label (str): The text on the button
        disabled (bool): Whether the button starts out disabled
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
        ----------
        interaction (discord.Interaction): The interaction that triggered this
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
        self, paginator: Paginator, owner: discord.User | discord.Member, content_constructor: callable = None
    ):
        """
        Parameters
        ----------
        paginator (Paginator): The paginator object that contains the data to be paginated
        owner (discord.User | discord.Member): The user that invoked the paginator. Only this user can use the buttons
        content_constructor (callable): A function that takes a paginator object and a page number and returns an embed
        """

        super().__init__()
        self.paginator = paginator
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
        ----------
        base_embed (discord.Embed): The base embed to add fields to
        """

        return self.content_constructor(self.paginator.get_current_page(), embed=base_embed)

    def __default_content_constructor(self, page: list, embed: discord.Embed) -> discord.Embed:
        """
        Default embed template for the paginator

        Parameters
        ----------
        page (list): The items to show on the page
        embed (discord.Embed): The embed to add the page to

        Returns
        ----------
        (discord.Embed): The embed with the page added
        """

        embed.description = "\n".join(page)
        embed.set_footer(text=f"Side {self.paginator.current_page}/{self.paginator.total_page_count}")
        return embed


@dataclass
class Lobby:
    """Players gathering before an activity starts. Closed once it starts, is deleted or times out"""

    host: discord.User
    players: list[discord.User]
    ends: datetime
    kicked_players: set[int] = field(default_factory=set)
    closed: bool = False


async def open_lobby(
    interaction: discord.Interaction,
    lobbies: dict[int, Lobby],
    view_class: type["LobbyView"],
    title: str,
    duration: timedelta,
):
    """
    Open a lobby hosted by the invoking user, unless they already host or are in an open lobby

    Parameters
    ----------
    interaction (discord.Interaction): The interaction that triggered this
    lobbies (dict[int, Lobby]): The cog's lobbies by host ID. The new lobby is added to it
    view_class (type[LobbyView]): The view to show the lobby with
    title (str): The title of the lobby message
    duration (timedelta): How long the lobby stays open
    """

    for host_id in [host_id for host_id, lobby in lobbies.items() if lobby.closed]:
        del lobbies[host_id]

    if interaction.user.id in lobbies:
        return await interaction.response.send_message(
            embed=embed_templates.error_warning("Du hoster allerede en lobby")
        )

    if any(interaction.user in lobby.players for lobby in lobbies.values()):
        return await interaction.response.send_message(embed=embed_templates.error_warning("Du er allerede i en lobby"))

    lobby = Lobby(host=interaction.user, players=[interaction.user], ends=discord.utils.utcnow() + duration)
    lobbies[interaction.user.id] = lobby

    time_left = discord.utils.format_dt(lobby.ends, "R")
    embed = discord.Embed(
        title=title, description=f"Lobbyen stenger {time_left}. Bli med innen da!", color=interaction.user.color
    )
    embed.set_author(name=interaction.user.global_name, icon_url=interaction.user.avatar)
    embed.add_field(name="Spillere", value=f"* {interaction.user.mention}", inline=False)

    view = view_class(lobby, interaction.client)
    await interaction.response.send_message(embed=embed, view=view)

    # Edit the message with the bot's own token later, since the interaction's token expires after 15 minutes
    response = await interaction.original_response()
    view.message = interaction.channel.get_partial_message(response.id)


class LobbyView(discord.ui.View):
    """Lobby players can join, leave and be kicked from. Subclasses decide what starting it does"""

    def __init__(self, lobby: Lobby, bot: commands.Bot):
        """
        Parameters
        ----------
        lobby (Lobby): The lobby to show
        bot (commands.Bot): The bot instance
        """

        lobby_end = (lobby.ends - discord.utils.utcnow()).total_seconds()
        super().__init__(timeout=lobby_end)

        self.lobby = lobby
        self.bot = bot
        self.message: discord.PartialMessage | None = None

        self.kick_menu = _KickSelectMenu(self)
        self.add_item(self.kick_menu)

    async def on_timeout(self):
        """
        Close the lobby and disable its buttons when it times out
        """

        await self.end_lobby()
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass  # The message has been deleted

    async def end_lobby(self):
        """
        Close the lobby, disable its buttons and stop listening for interactions
        """

        self.lobby.closed = True
        for item in self.children:
            item.disabled = True
        self.stop()

    async def rerender_players(self, interaction: discord.Interaction):
        """
        Update the player list and the kick menu in the lobby message

        Parameters
        ----------
        interaction (discord.Interaction): The interaction that triggered this
        """

        self.kick_menu.update_options()
        embed = interaction.message.embeds[0].set_field_at(
            0,
            name=f"Spillere ({len(self.lobby.players)})",
            value="\n".join([f"* {p.mention}" for p in self.lobby.players]),
        )
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Bli med", style=discord.ButtonStyle.blurple)
    async def join_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Add the user to the lobby

        Parameters
        ----------
        interaction (discord.Interaction): The interaction that triggered this
        button (discord.ui.Button): The button that was pressed
        """

        if self.lobby.closed:
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
        """
        Close the lobby. Subclasses override this to start their activity

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

        embed = interaction.message.embeds[0]
        embed.description = "Lobbyen har startet!"
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Forlat", style=discord.ButtonStyle.gray)
    async def leave_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Remove the user from the lobby

        Parameters
        ----------
        interaction (discord.Interaction): The interaction that triggered this
        button (discord.ui.Button): The button that was pressed
        """

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
        """
        Close the lobby and delete its message

        Parameters
        ----------
        interaction (discord.Interaction): The interaction that triggered this
        button (discord.ui.Button): The button that was pressed
        """

        if interaction.user != self.lobby.host:
            embed = embed_templates.error_warning("Bare hosten kan slette lobbyen")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        await self.end_lobby()
        await interaction.message.delete()

        embed = embed_templates.success("Lobbyen har blitt slettet")
        await interaction.response.send_message(embed=embed, delete_after=5)


class _KickSelectMenu(discord.ui.Select):
    """Menu the host uses to kick players from the lobby"""

    def __init__(self, parent_view: LobbyView):
        """
        Parameters
        ----------
        parent_view (LobbyView): The lobby view the menu belongs to
        """

        self.parent_view = parent_view
        super().__init__(placeholder="Kick en spiller", max_values=1, min_values=1)
        self.update_options()

    def update_options(self):
        """
        Lists the lobby's current players as options
        """

        self.options = [
            discord.SelectOption(
                label=p.display_name, value=str(p.id), emoji="🔨", description=f"Kick {p.display_name}"
            )
            for p in self.parent_view.lobby.players
        ]

    async def callback(self, interaction: discord.Interaction):
        """
        Kick the selected player from the lobby

        Parameters
        ----------
        interaction (discord.Interaction): The interaction that triggered this
        """

        if interaction.user != self.parent_view.lobby.host:
            embed = embed_templates.error_warning("Bare hosten kan kicke spillere")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        if str(interaction.user.id) == interaction.data["values"][0]:
            embed = embed_templates.error_warning("Du kan ikke kicke deg selv")
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

        self.parent_view.lobby.kicked_players.add(int(interaction.data["values"][0]))

        # Remove the player from the lobby
        # Since we only have the ID, we have to iterate through the list
        # unless we want to fetch the member object from the API
        # which we don't :)
        for i, member in enumerate(self.parent_view.lobby.players):
            if member.id == int(interaction.data["values"][0]):
                self.parent_view.lobby.players.pop(i)
                break

        await self.parent_view.rerender_players(interaction)

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
        self.db = getattr(bot, "db", None)  # Channels are only remembered across restarts if there is a database
        self.temp_vc_channels = {}

    async def start(self):
        """
        Create the table used to remember temporary channels across restarts and start the cleanup loop
        """

        if self.db:
            await self.db.execute("""
                CREATE TABLE IF NOT EXISTS tempvoice_channels (
                    channel_id BIGINT PRIMARY KEY
                );
                """)

        self.check_temp_vc_channels.start()

    async def remember(self, channel: discord.VoiceChannel):
        """
        Save a temporary channel so it can still be deleted if the bot restarts

        Parameters
        ----------
        channel (discord.VoiceChannel): The temporary channel
        """

        if not self.db:
            return

        try:
            await self.db.execute(
                "INSERT INTO tempvoice_channels (channel_id) VALUES (%s) ON CONFLICT DO NOTHING", (channel.id,)
            )
        except psycopg.Error as e:
            self.bot.logger.warning(
                f"Failed to save temporary voice channel {channel}. It won't survive a restart: {e}"
            )

    async def forget(self, channel_id: int):
        """
        Remove a saved temporary channel

        Parameters
        ----------
        channel_id (int): The ID of the temporary channel
        """

        if not self.db:
            return

        try:
            await self.db.execute("DELETE FROM tempvoice_channels WHERE channel_id = %s", (channel_id,))
        except psycopg.Error as e:
            self.bot.logger.warning(f"Failed to remove saved temporary voice channel {channel_id}: {e}")

    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        """
        Listen for disconnects from the temporary voice channels

        Parameters
        ----------
        member (discord.Member): The member whose voice state changed
        before (discord.VoiceState): The voice state before the change
        after (discord.VoiceState): The voice state after the change
        """

        for channel in (before.channel, after.channel):
            if channel not in self.temp_vc_channels:
                continue

            if len(channel.members) == 0:
                self.temp_vc_channels[channel]["no_members_since"] = discord.utils.utcnow()
                self.bot.logger.info(f"Temporary voice channel {channel} has no members. Will be deleted in 1 minutes")
            else:
                self.temp_vc_channels[channel]["no_members_since"] = None

    @tasks.loop(minutes=1)
    @log_errors
    async def check_temp_vc_channels(self):
        """
        Check for temporary voice channels that have been inactive for 1 minute
        """

        for channel, data in self.temp_vc_channels.copy().items():
            if not data["no_members_since"]:
                continue

            if (discord.utils.utcnow() - data["no_members_since"]).total_seconds() >= 60:
                try:
                    await channel.delete(reason="tempvoice kanal inaktiv i 1 minutt")
                except discord.NotFound:
                    self.bot.logger.info(f"Temporary voice channel {channel} was already deleted")
                except discord.Forbidden:
                    self.bot.logger.info(f"Failed to delete temporary voice channel {channel}")
                else:
                    self.bot.logger.info(f"Deleted temporary voice channel {channel}")
                finally:
                    del self.temp_vc_channels[channel]
                    await self.forget(channel.id)

    @check_temp_vc_channels.before_loop
    async def restore_temp_vc_channels(self):
        """
        Pick up temporary channels created before the bot last stopped, so they still get deleted
        """

        await self.bot.wait_until_ready()

        if not self.db:
            return

        try:
            saved_channels = await self.db.fetchall("SELECT channel_id FROM tempvoice_channels")
        except psycopg.Error as e:
            self.bot.logger.warning(f"Failed to restore temporary voice channels: {e}")
            return

        restored = 0
        for (channel_id,) in saved_channels:
            if not (channel := self.bot.get_channel(channel_id)):
                await self.forget(channel_id)
                continue

            now = discord.utils.utcnow()
            self.temp_vc_channels[channel] = {"created": now, "no_members_since": None if channel.members else now}
            restored += 1

        if restored:
            self.bot.logger.info(f"Restored {restored} temporary voice channel(s) from the database")

    async def create_temp_voice(
        self, interaction: discord.Interaction, name: str, limit: int = 0
    ) -> discord.VoiceChannel | None:
        """
        Create a temporary voice channel

        Parameters
        ----------
        interaction (discord.Interaction): The interaction that triggered this
        name (str): The name of the channel
        limit (int): The user limit of the channel

        Returns
        ----------
        (discord.VoiceChannel | None): The new channel. None if it couldn't be created
        """

        # Get the UiO Gaming server's VC category. If the command is not invoked in that server it should still be fine
        # since the it will return None if not found.
        vc_category = interaction.guild.get_channel(self.bot.channel_ids.get("voice_category"))

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

        now = discord.utils.utcnow()
        self.temp_vc_channels[channel] = {"created": now, "no_members_since": now}
        await self.remember(channel)

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
        interaction (discord.Interaction): The interaction that triggered this
        channel (discord.VoiceChannel): The channel the users should be moved to
        users (list[discord.User]): A list of users to be moved

        Returns
        ----------
        (list[discord.User]): The users that couldn't be moved. Empty if everyone was moved
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
