import discord
from discord import app_commands
from discord.ext import commands

from cogs.utils import discord_utils
from cogs.utils import embed_templates
from cogs.utils import misc_utils


class Info(commands.Cog):
    """View information about Discord object such as guilds, users, roles and channels"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot

    guild_group = app_commands.Group(name="guild", description="Se ting om serveren")
    user_group = app_commands.Group(name="bruker", description="Se ting om brukeren")

    def construct_role_string(self, roles: list[discord.Role]) -> str:
        """
        Puts all roles except @everyone into a list and joins them to a string

        Parameters
        ----------
        roles (list[discord.Role]): List of roles

        Returns
        -------
        (str): String of roles
        """

        if not roles:
            return "**Ingen roller**"

        roles = [role.name for role in roles if role.name != "@everyone"]
        roles.reverse()

        return ", ".join(roles)

    def construct_booster_string(self, interaction: discord.Interaction, join_method: callable = ", ".join) -> str:
        """
        Joins all boosters into a string

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        join_method (callable): Function to join the boosters with

        Returns
        -------
        (str): String of boosters
        """

        if not interaction.guild.premium_subscribers:
            return "**Ingen boostere**"

        # Sort boosters by boost date and put name as well as date of boost into a list of stirngs
        boosters = [
            f"* {b.name} - {discord.utils.format_dt(b.premium_since)}"
            for b in sorted(interaction.guild.premium_subscribers, key=lambda m: m.premium_since)
        ]

        return join_method(boosters)

    def construct_member_string(self, members: list[discord.Member]) -> str:
        """
        Joins all names into a string

        Parameters
        ----------
        members (list[discord.Member]): List of members

        Returns
        -------
        (str): String of members
        """

        if not members:
            return "**Ingen**"

        members = [member.name for member in members]

        return ", ".join(members)

    @app_commands.guild_only()
    @app_commands.checks.bot_has_permissions(embed_links=True, external_emojis=True)
    @app_commands.checks.cooldown(1, 2)
    @guild_group.command(name="info", description="Hent informasjon om en server")
    async def guild_info(self, interaction: discord.Interaction):
        """
        Sends general information about the guild

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        # Days since guild was created
        creation_date_timestamp = discord.utils.format_dt(interaction.guild.created_at, style="F")
        since_created_days = (interaction.created_at - interaction.guild.created_at).days
        days_ago = f"{since_created_days} dager" if since_created_days != 1 else f"{since_created_days} dag"

        # Member count and status counts
        total_members = interaction.guild.member_count
        bot_members = 0
        online_members = 0
        idle_members = 0
        dnd_members = 0
        offline_members = 0
        for member in interaction.guild.members:
            if member.bot:
                bot_members += 1
            if str(member.status) == "online":
                online_members += 1
            elif str(member.status) == "idle":
                idle_members += 1
            elif str(member.status) == "dnd":
                dnd_members += 1
            elif str(member.status) == "offline":
                offline_members += 1

        # Roles
        roles = self.construct_role_string(interaction.guild.roles)
        roles = (
            roles
            if len(roles) < 1024
            else f"Bruk `/{self.bot.tree.get_command('guild').get_command('roller').qualified_name}` for å se rollene"
        )

        # Boosts
        boosters = self.construct_booster_string(interaction, join_method="\n".join)
        boosters = (
            boosters
            if len(boosters) < 1024
            else f"Bruk `/{self.bot.tree.get_command('guild').get_command('boosters').qualified_name}` for å se boostere"  # noqa: E501
        )

        # Channels counts
        text_channels = len(interaction.guild.text_channels)
        voice_channels = len(interaction.guild.voice_channels)
        categories = len(interaction.guild.categories)
        total_channels = text_channels + voice_channels

        # Features
        features_string = ""
        if interaction.guild.features != []:
            features = {
                "ANIMATED_BANNER": "Animer serverbanner",
                "ANIMATED_ICON": "Animert serverikon",
                "APPLICATION_COMMAND_PERMISSIONS_V2": "Gamle slash command tillatelser",
                "AUTO_MODERATION": "Automoderering",
                "BANNER": "Serverbanner",
                "COMMUNITY": "Samfunnsserver",
                "CREATOR_MONETIZABLE_PROVISIONAL": "Betalingsmuligheter",
                "CREATOR_STORE_PAGE": "Abonnomentsside",
                "DEVELOPER_SUPPORT_SERVER": "Støtteserver for utviklere",
                "DISCOVERABLE": "På utforsksiden",
                "FEATURABLE": "Fremhevbar",
                "INVITES_DISABLED": "Invitasjoner deaktivert",
                "INVITE_SPLASH": "Invitasjonsbilde",
                "MEMBER_VERIFICATION_GATE_ENABLED": "Medlemsverifisering",
                "MORE_STICKERS": "Flere stickers",
                "NEWS": "Nyhetskanaler",
                "PARTNERED": "Partner",
                "PREVIEW_ENABLED": "Forhåndsvisning",
                "RAID_ALERTS_DISABLED": "Raidvarsler deaktivert",
                "ROLE_ICONS": "Rolleikon",
                "ROLE_SUBSCRIPTIONS_AVAILABLE_FOR_PURCHASE": "Abonomentsroller tilgjengelig",
                "ROLE_SUBSCRIPTIONS_ENABLED": "Abonomentsroller aktivert",
                "TICKETED_EVENTS_ENABLED": "Arrangmenter med billettsalg",
                "VANITY_URL": "Egendefinert URL",
                "VERIFIED": "Verifisert",
                "VIP_REGIONS": "Høyere bitrate i stemmekanaler",
                "WELCOME_SCREEN_ENABLED": "Velkomstskjerm",
            }
            for feature in interaction.guild.features:
                if translation := features.get(feature):
                    features_string += f"* {translation}\n"

        photos = {}
        if interaction.guild.splash:
            photos["Invitasjonsbilde"] = interaction.guild.splash
        if interaction.guild.banner:
            photos["Banner"] = interaction.guild.banner

        verification_level = {
            "none": "ingen",
            "low": "e-post",
            "medium": "e-post, registrert i 5 min",
            "high": "e-post, registrert i 5 min, medlem i 10 min",
            "extreme": "telefon",
        }
        verification = verification_level[str(interaction.guild.verification_level)]

        content_filter = {"disabled": "nei", "no_role": "for alle uten rolle", "all_members": "ja"}
        content = content_filter[str(interaction.guild.explicit_content_filter)]

        embed = discord.Embed(
            color=interaction.guild.me.color,
            description=f"* **Verifiseringskrav:** {verification}\n"
            + f"* **Innholdsfilter:** {content}\n"
            + f"* **Boost Tier:** {interaction.guild.premium_tier}\n"
            + f"* **Emoji:** {len(interaction.guild.emojis)}\n"
            + f"* **Stickers:** {len(interaction.guild.stickers)}\n",
        )
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon)
        embed.set_thumbnail(url=interaction.guild.icon)
        embed.add_field(name="ID", value=interaction.guild.id)
        embed.add_field(name="Eier", value=interaction.guild.owner.mention)
        embed.add_field(name="Opprettet", value=f"{creation_date_timestamp}\n{days_ago} siden")
        embed.add_field(
            name=f"Kanaler ({total_channels})",
            value=f"💬 Tekst: **{text_channels}**\n"
            + f"🔊 Tale: **{voice_channels}**\n"
            + f"🗃️ Kategorier: **{categories}**",
        )
        embed.add_field(
            name=f"Medlemmer ({total_members})",
            value=f"👤 Mennesker: **{int(total_members) - int(bot_members)}**\n"
            + f"🤖 Båtter: **{bot_members}**\n"
            + f'{self.bot.emoji["online"]}{online_members} '
            + f'{self.bot.emoji["idle"]}{idle_members} '
            + f'{self.bot.emoji["dnd"]}{dnd_members} '
            + f'{self.bot.emoji["offline"]}{offline_members}',
        )
        embed.add_field(name=f"Roller ({len(interaction.guild.roles) - 1})", value=roles, inline=False)
        if interaction.guild.premium_tier != 0:
            embed.add_field(
                name=f"Boosts ({interaction.guild.premium_subscription_count})", value=boosters, inline=False
            )

        if features_string:
            embed.add_field(name="Tillegsfunksjoner", value=features_string)

        if photos:
            photos_string = ""
            for key, value in photos.items():
                photos_string += f"* [{key}]({value})\n"
            embed.add_field(name="Bilder", value=photos_string)
        await interaction.response.send_message(embed=embed)

    @app_commands.guild_only()
    @app_commands.checks.bot_has_permissions(embed_links=True, attach_files=True)
    @app_commands.checks.cooldown(1, 2)
    @guild_group.command(name="roller", description="Se rollene på serveren")
    async def guild_roles(self, interaction: discord.Interaction):
        """
        List all roles in the guild

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        roles = self.construct_role_string(interaction.guild.roles)

        # IF roles list is longer than 2048, create text file and send it
        if len(roles) > 2048:
            await discord_utils.send_as_txt_file(interaction, roles, f"./assets/temp/{interaction.guild.id}_roles.txt")
        else:
            embed = discord.Embed(color=interaction.guild.me.color, description=roles)
            embed.set_author(name=f"Roller ({len(interaction.guild.roles)})", icon_url=interaction.guild.icon)
            embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon)
            await interaction.response.send_message(embed=embed)

    @app_commands.guild_only()
    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @guild_group.command(name="boosters", description="Se boostere på serveren")
    async def guild_boosters(self, interaction: discord.Interaction):
        """
        List all boosters in the guild

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        if len(interaction.guild.premium_subscribers) == 0:
            embed = embed_templates.error_warning("Serveren har ikke noen boosts :(")
            return await interaction.response.send_message(embed=embed)

        boosters = self.construct_booster_string(interaction, "\n".join)

        embed = discord.Embed(color=interaction.guild.me.color, description=boosters)
        embed.set_author(
            name=f"Boosts ({interaction.guild.premium_subscription_count})", icon_url=interaction.guild.icon
        )
        embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon)
        await interaction.response.send_message(embed=embed)

    @app_commands.guild_only()
    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @guild_group.command(name="ikon", description="Hent serverens ikon")
    async def guild_icon(self, interaction: discord.Interaction):
        """
        Get the guild icon

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        embed = discord.Embed(color=interaction.guild.me.color, description=f"[Lenke]({interaction.guild.icon})")
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon)
        embed.set_image(url=interaction.guild.icon)
        await interaction.response.send_message(embed=embed)

    @app_commands.guild_only()
    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @guild_group.command(name="splash", description="Hent serverens splash (bakgrunnsbilde på invitasjonsside)")
    async def guild_splash(self, interaction: discord.Interaction):
        """
        Get the guild splash

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        if not interaction.guild.splash:
            embed = embed_templates.error_warning("Serveren har ikke en splash")
            return await interaction.response.send_message(embed=embed)

        embed = discord.Embed(color=interaction.guild.me.color, description=f"[Lenke]({interaction.guild.splash})")
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon)
        embed.set_image(url=interaction.guild.splash)
        await interaction.response.send_message(embed=embed)

    @app_commands.guild_only()
    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @guild_group.command(name="banner", description="Hen serverens banner")
    async def guild_banner(self, interaction: discord.Interaction):
        """
        Get the guild banner

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        if not interaction.guild.banner:
            embed = embed_templates.error_warning("Serveren har ikke et banner :(")
            return await interaction.response.send_message(embed=embed)

        embed = discord.Embed(color=interaction.guild.me.color, description=f"[Lenke]({interaction.guild.banner})")
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon)
        embed.set_image(url=interaction.guild.banner)
        await interaction.response.send_message(embed=embed)

    @app_commands.guild_only()
    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @guild_group.command(name="rolle", description="Hent informasjon om en rolle på serveren")
    async def guild_role(self, interaction: discord.Interaction, rolle: discord.Role):
        """
        Get information about a role

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        rolle (discord.Role): Role to fetch information about
        """

        if rolle.name == "@everyone":
            embed = embed_templates.error_warning("Skriv inn en annen rolle enn `@everyone`")
            return await interaction.response.send_message(embed=embed)

        # Timestamp and days since creation
        created_at_timestamp = discord.utils.format_dt(rolle.created_at, style="F")
        since_created_days = (interaction.created_at - rolle.created_at).days

        # List of members with the role
        members = self.construct_member_string(rolle.members)
        members = members if len(members) < 1024 else "For mange medlemmer for å vise her"

        # List of permissions
        permissions = ", ".join([permission for permission, value in iter(rolle.permissions) if value is True])

        embed = discord.Embed(title=rolle.name, description=f"{rolle.mention}\n**ID:** {rolle.id}", color=rolle.color)
        embed.set_author(name=rolle.guild.name, icon_url=rolle.guild.icon)
        embed.add_field(name="Fargekode", value=str(rolle.color))
        embed.add_field(
            name="Opprettet",
            value=f"{created_at_timestamp}\n{since_created_days} "
            + f'{"dager" if since_created_days != 1 else "dag"} siden',
        )
        embed.add_field(name="Posisjon", value=rolle.position)
        embed.add_field(name="Nevnbar", value="Ja" if rolle.mentionable else "Nei")
        embed.add_field(name="Vises separat i medlemsliste", value="Ja" if rolle.hoist else "Nei")
        if permissions:
            embed.add_field(name="Tillatelser", value=permissions, inline=False)
        embed.add_field(name=f"Brukere med rollen ({len(rolle.members)})", value=members, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.guild_only()
    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @guild_group.command(name="tekstkanal", description="Hent informasjon om en tekstkanal")
    async def guild_text_channel(self, interaction: discord.Interaction, kanal: discord.TextChannel):
        """
        Get information about a text channel

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        kanal (discord.TextChannel): Text channel to fetch information about
        """

        members = self.construct_member_string(kanal.members)
        if len(members) > 1024:
            members = "For mange for å vise her"

        embed = discord.Embed(
            color=interaction.guild.me.color, title=kanal.name, description=f"{kanal.mention}\nID: {kanal.id}"
        )
        embed.set_author(name=kanal.guild.name, icon_url=kanal.guild.icon)
        embed.add_field(name="Beskrivelse", value=kanal.topic if kanal.topic else "**Ingen**", inline=False)
        embed.add_field(name="Opprettet", value=discord.utils.format_dt(kanal.created_at, style="F"))
        embed.add_field(name="NSFW", value="Ja" if kanal.is_nsfw() else "Nei")
        embed.add_field(
            name="Saktemodus", value=f"Ja ({kanal.slowmode_delay} sekunder)" if kanal.slowmode_delay else "Nei"
        )
        if kanal.category:
            embed.add_field(name="Kategori", value=kanal.category.name)
        embed.add_field(name=f"Antall med tilgang ({len(kanal.members)})", value=members)
        await interaction.response.send_message(embed=embed)

    @app_commands.guild_only()
    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @guild_group.command(name="talekanal", description="Hent informasjon om en talekanal")
    async def guild_voice_channel(self, interaction: discord.Interaction, kanal: discord.VoiceChannel):
        """
        Get information about a voice channel

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        kanal (discord.VoiceChannel): Voice channel to fetch information about
        """

        embed = discord.Embed(color=interaction.guild.me.color, title=kanal.name, description=f"ID: {kanal.id}")
        embed.set_author(name=kanal.guild.name, icon_url=kanal.guild.icon)
        embed.add_field(name="Opprettet", value=discord.utils.format_dt(kanal.created_at, style="F"))
        embed.add_field(name="Bitrate", value=f"{int(kanal.bitrate / 1000)}kbps")
        embed.add_field(
            name="Maksgrense", value=f"{kanal.user_limit} personer" if kanal.user_limit != 0 else "∞ personer"
        )
        if kanal.category:
            embed.add_field(name="Kategori", value=kanal.category.name)
        embed.add_field(name="Antall koblet til", value=len(kanal.members))
        await interaction.response.send_message(embed=embed)

    @app_commands.guild_only()
    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 5)
    @guild_group.command(name="topproller", description="Viser rollene med flest brukere i kronologisk rekkefølge")
    async def guild_top_roles(self, interaction: discord.Interaction):
        """
        Show the roles with the most users in chronological order

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        roles = sorted(
            [r for r in interaction.guild.roles if r.name != "@everyone"], key=lambda x: len(x.members), reverse=True
        )
        roles_formatted = [f"**#{i + 1}** {r.mention} - {len(r.members)}" for i, r in enumerate(roles)]

        paginator = misc_utils.Paginator(roles_formatted)
        view = discord_utils.Scroller(paginator, interaction.user)

        embed = view.construct_embed(
            discord.Embed(color=interaction.guild.me.color, title="Rollene med flest brukere på serveren")
        )
        await interaction.response.send_message(embed=embed, view=view)

    @commands.guild_only()
    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @app_commands.command(name="emoji", description="Hent informasjon om en emoji i serveren")
    async def emoji(self, interaction: discord.Interaction, emoji: str):
        """
        Get information about an emoji in the server

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        emoji (discord.Emoji): Emoji to fetch information about
        """

        emoji = discord.PartialEmoji.from_str(emoji)

        if not emoji.is_custom_emoji():
            embed = embed_templates.error_warning("Denne kommandoen støtter bare serveremoji")
            return await interaction.response.send_message(embed=embed)

        emoji = discord.utils.get(interaction.guild.emojis, name=emoji.name)
        if not emoji:
            embed = embed_templates.error_warning("Emoji kunne ikke hentes. Den er muligens fra en annen server")
            return await interaction.response.send_message(embed=embed)

        self.bot.logger.info(emoji)
        try:
            emoji_creator = f"{emoji.user.mention}\n{emoji.user.name}"
        except AttributeError:
            emoji_creator = "Jeg trenger `manage_emojis`-tillatelsen på serveren den er fra for å hente dette"

        embed = discord.Embed(title=emoji.name, description=f"ID: {emoji.id}")
        embed.set_author(name=emoji.guild.name, icon_url=emoji.guild.icon)
        embed.add_field(name="Opprettet", value=discord.utils.format_dt(emoji.created_at, style="F"))
        embed.add_field(name="Animert", value="Ja" if emoji.animated else "Nei")
        embed.add_field(name="Lagt til av", value=emoji_creator)
        embed.set_image(url=emoji.url)
        await interaction.response.send_message(embed=embed)

    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 2, commands.BucketType.user)
    @commands.command(name="sticker", description="Hent informasjon om en sticker på serveren")
    async def sticker(self, ctx: commands.Context):
        """
        Get information about a sticker in the server

        Parameters
        ----------
        ctx (commands.Context): Command context object
        """

        if ctx.message.type != discord.MessageType.reply:
            embed = embed_templates.error_warning("Du må svare på en melding som inneholder en sticker")
            return await ctx.reply(embed=embed)

        if ctx.message.reference and isinstance(ctx.message.reference.resolved, discord.Message):
            replied_message = ctx.message.reference.resolved
        elif ctx.message.reference:
            try:
                replied_message = await ctx.message.channel.fetch_message(ctx.message.reference.message_id)
            except discord.NotFound:
                embed = embed_templates.error_warning("Kunne ikke hente meldingen du svarte på")
                return await ctx.reply(embed=embed)

        sticker = await replied_message.guild.fetch_sticker(replied_message.stickers[0].id)
        if not sticker:
            embed = embed_templates.error_warning("Sticker kunne ikke hentes")
            return await ctx.reply(embed=embed)

        embed = discord.Embed(title=sticker.name, description=f"ID: {sticker.id}\n\n{sticker.description}")
        embed.set_author(name=sticker.guild.name, icon_url=sticker.guild.icon)
        embed.add_field(name="Opprettet", value=discord.utils.format_dt(sticker.created_at, style="F"))
        embed.add_field(name="Format", value=str(sticker.format).split(".")[-1].upper())
        embed.add_field(name="Emoji", value=sticker.emoji)
        embed.add_field(name="Lagt til av", value=sticker.user.mention if sticker.user else "Ikke tilgjengelig")
        embed.set_image(url=sticker.url)
        await ctx.reply(embed=embed)

    guild_oldest_group = app_commands.Group(
        name="eldst", description="Viser de eldste medlemmene på serveren", parent=guild_group
    )

    @commands.guild_only()
    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 5)
    @guild_oldest_group.command(
        name="lagd", description="Liste over de eldste brukerene på serveren basert på når de ble lagd"
    )
    async def guild_user_created_oldest(self, interaction: discord.Interaction):
        """
        List the oldest users on the server based on when they were created

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        # Sort members by creation date
        members = sorted(interaction.guild.members, key=lambda m: m.created_at)

        # Create list of members with index, name and creation date
        members_formatted = [
            f"**#{i+1}** {m.name} - {discord.utils.format_dt(m.created_at, style='F')}" for i, m in enumerate(members)
        ]

        paginator = misc_utils.Paginator(members_formatted)
        view = discord_utils.Scroller(paginator, interaction.user)

        embed = view.construct_embed(
            discord.Embed(
                color=interaction.guild.me.color, title="Eldste brukere på serveren basert på når de ble lagd"
            )
        )
        await interaction.response.send_message(embed=embed, view=view)

    @commands.guild_only()
    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 5)
    @guild_oldest_group.command(
        name="joined", description="Liste over de eldste brukerene på serveren basert på når de ble med"
    )
    async def guild_user_joined_oldest(self, interaction: discord.Interaction):
        """
        List the oldest users on the server based on when they joined

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        # Sort members by creation date
        members = sorted(interaction.guild.members, key=lambda m: m.joined_at)

        # Create list of members with index, name#discriminator and creation date
        members_formatted = [
            f"**#{i+1}** {m.name} - {discord.utils.format_dt(m.joined_at, style='F')}" for i, m in enumerate(members)
        ]

        paginator = misc_utils.Paginator(members_formatted)
        view = discord_utils.Scroller(paginator, interaction.user)

        # Send first page
        embed = view.construct_embed(
            discord.Embed(color=interaction.guild.me.color, title="Eldste brukere på serveren basert på når de ble med")
        )
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.guild_only()
    @app_commands.checks.bot_has_permissions(embed_links=True, external_emojis=True)
    @app_commands.checks.cooldown(1, 2)
    @user_group.command(name="info", description="Hent informasjon om en bruker")
    async def user_info(self, interaction: discord.Interaction, *, bruker: discord.Member | None = None):
        """
        Get information about a user

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        bruker (discord.Member, optional): User to get information about. Defaults to None (invoker).
        """

        if not bruker:
            bruker = interaction.user

        # Get device(s) that is currently used by the user
        app = ""
        if str(bruker.mobile_status) != "offline":
            app += "📱 "
        if str(bruker.web_status) != "offline":
            app += "🌐 "
        if str(bruker.desktop_status) != "offline":
            app += "💻"

        # Get index of join, creation and/or boost date in comparison to other users in the guild
        join_index = sorted(interaction.guild.members, key=lambda m: m.joined_at).index(bruker) + 1
        creation_index = sorted(interaction.guild.members, key=lambda m: m.created_at).index(bruker) + 1
        if bruker.premium_since:
            premium_index = (
                sorted(interaction.guild.premium_subscribers, key=lambda m: m.premium_since).index(bruker) + 1
            )

        #  Creation/join date & days ago
        created_timestamp = discord.utils.format_dt(bruker.created_at, style="F")
        joined_timestamp = discord.utils.format_dt(bruker.joined_at, style="F")
        joined_days = (interaction.created_at - bruker.joined_at).days
        created_days = (interaction.created_at - bruker.created_at).days

        # Boost date & days ago
        if bruker.premium_since:
            premium_since = discord.utils.format_dt(bruker.premium_since, style="F")
            premium_since_days = (interaction.created_at - bruker.premium_since).days

        # Get user roles
        roles = self.construct_role_string(bruker.roles)

        roles = (
            roles
            if len(roles) < 1024
            else f'Bruk `/{self.bot.tree.get_command("bruker").get_command("roller").qualified_name}` for å se rollene'
        )

        statuses = {
            "online": f'{self.bot.emoji["online"]} Pålogget',
            "idle": f'{self.bot.emoji["idle"]} Inaktiv',
            "dnd": f'{self.bot.emoji["dnd"]} Ikke forstyrr',
            "offline": f'{self.bot.emoji["offline"]} Frakoblet',
        }
        status = statuses[str(bruker.status)]

        embed = discord.Embed(color=bruker.color, description=f"{bruker.mention}\nID: {bruker.id}\n{status}\n{app}")
        if bruker.display_name == bruker.name:
            embed.set_author(name=bruker.name, icon_url=bruker.display_avatar)
        else:
            embed.set_author(name=f"{bruker.name} | {bruker.display_name}", icon_url=bruker.display_avatar)
        embed.set_thumbnail(url=bruker.display_avatar)
        embed.add_field(
            name="Opprettet",
            value=f"{created_timestamp}\n{created_days} " + f'{"dag" if created_days == 1 else "dager"} siden',
        )
        embed.add_field(
            name="Ble med i serveren",
            value=f"{joined_timestamp}\n{joined_days} " + f'{"dag" if joined_days == 1 else "dager"} siden',
        )
        if bruker.premium_since:
            embed.add_field(
                name="Boost",
                value=f"{premium_since}\n{premium_since_days} "
                + f'{"dag" if premium_since_days == 1 else "dager"} siden\n'
                + f"Booster #{premium_index} av serveren",
                inline=False,
            )
        embed.add_field(name=f"Roller ({len(bruker.roles)})", value=roles, inline=False)
        embed.set_footer(text=f"#{join_index} Medlem av serveren | #{creation_index} Eldste brukeren på serveren")

        # Playing activity
        if bruker.activities:
            games = ""
            for activity in bruker.activities:
                games += f"{activity.name}\n"
            if games:
                embed.add_field(name="Spiller", value=games, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.guild_only()
    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @user_group.command(name="roller", description="Hent roller til en bruker")
    async def user_roles(self, interaction: discord.Interaction, bruker: discord.Member | None = None):
        """
        Get roles of a user

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        bruker (discord.Member, optional): User to get roles of. Defaults to None (invoker).
        """

        if not bruker:
            bruker = interaction.user

        roles = self.construct_role_string(bruker.roles)

        # If the list of roles is too long, send it as a file
        if len(roles) > 2048:
            await discord_utils.send_as_txt_file(
                interaction, roles, f"./assets/temp/{interaction.guild.id}_{interaction.user.id}_roles.txt"
            )
        else:
            embed = discord.Embed(color=bruker.color, description=roles)
            embed.set_author(name=f"Roller ({len(bruker.roles)})", icon_url=bruker.display_avatar)
            embed.set_footer(text=bruker.name, icon_url=bruker.display_avatar)
            await interaction.response.send_message(embed=embed)

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @user_group.command(name="avatar", description="Hent avatar til en bruker")
    async def user_avatar(self, interaction: discord.Interaction, bruker: discord.User | discord.Member | None = None):
        """
        Get avatar of a user

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        bruker (discord.User, optional): User to get avatar of. Defaults to None (invoker).
        """

        if not bruker:
            bruker = interaction.user

        embed = discord.Embed(color=bruker.color, description=f"[Lenke]({bruker.display_avatar})")
        embed.set_author(name=bruker.name, icon_url=bruker.display_avatar)
        embed.set_image(url=bruker.display_avatar)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(Info(bot))
