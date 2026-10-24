import re
from datetime import datetime

import discord
import requests
from discord import app_commands
from discord.ext import commands

from cogs.utils import embed_templates


class Anime(commands.Cog):
    """View information about different media on Anilist"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.anilist_logo = "https://anilist.co/img/logo_al.png"

    anilist = app_commands.Group(name="anilist", description="Hent informasjon fra Anilist")
    anilist_profile = app_commands.Group(
        parent=anilist, name="profil", description="Hent informasjon om en bruker på Anilist"
    )

    def convert_color(self, color: str) -> int:
        """
        Converts anilist colors to hext

        Parameters
        ----------
        color (str): The color string returned from the Anilist API

        Returns
        ----------
        (int): The color in hex for use in discord embeds
        """

        colors = {
            "blue": 0x3DB4F2,
            "purple": 0xC063FF,
            "pink": 0xFC9DD6,
            "orange": 0xEF881A,
            "red": 0xE13333,
            "green": 0x4CCA51,
            "gray": 0x677B94,
        }
        return colors.get(color, 0x677B94)

    def convert_media_format(self, media_format: str) -> str:
        """
        Translates media format names into norwegian

        Parameters
        ----------
        media_format (str): The english media format name returned from the Anilist API

        Returns
        ----------
        (str): The media format name in norwegian. If a translation doesn't exist it returns the english name
        """

        media_formats = {
            "TV": "TV-Serie",
            "TV_SHORT": "Kort TV-Serie",
            "MOVIE": "Film",
            "SPECIAL": "Ekstramateriale",
            "MUSIC": "Musikk",
            "MANGA": "Manga",
            "NOVEL": "Novelle",
            "ONE_SHOT": "Kort Manga",
        }
        return media_formats.get(media_format, media_format)

    def convert_language_names(self, language_name: str) -> str:
        """
        Translates language names into norwegian

        Parameters
        ----------
        language_name (str): The english language name returned from the Anilist API

        Returns
        ----------
        (str): The language name in norwegian. If a translation doesn't exist it returns the english name
        """

        languages = {
            "JAPANESE": "Japansk",
            "ENGLISH": "Engelsk",
            "KOREAN": "Koreansk",
            "ITALIAN": "Italiensk",
            "SPANISH": "Spansk",
            "PORTUGUESE": "Portugisisk",
            "FRENCH": "Fransk",
            "GERMAN": "Tysk",
            "HEBREW": "Hebraisk",
            "HUNGARIAN": "Ungarsk",
        }
        return languages.get(language_name, language_name)

    def onvert_role_names(self, role_name: str) -> str:
        """
        Translates role names into norwegian

        Parameters
        ----------
        role_name (str): The english role name returned from the Anilist API

        Returns
        ----------
        (str): The role name in norwegian. If a translation doesn't exist it returns the english name
        """

        roles = {"MAIN": "Hovedkarakter", "SUPPORTING": "Bikarakter/Biperson", "BACKGROUND": "Statist"}
        try:
            return roles[role_name]
        except KeyError:
            return role_name

    def convert_status(self, status: str) -> str:
        """
        Translates role names into norwegian

        Parameters
        ----------
        status (str): The english status name returned from the Anilist API

        Returns
        ----------
        (str): The status name in norwegian. If a translation doesn't exist it returns the english name
        """

        statuses = {
            "FINISHED": "Fullt utgitt",
            "RELEASING": "Pågående",
            "NOT_YET_RELEASED": "Ikke utgitt enda",
            "CANCELLED": "Kansellert",
        }
        return statuses.get(status, status)

    def remove_html(self, text: str) -> str:
        """
        Removes HTML tag elements

        Parameters
        ----------
        text: The raw HTML

        Returns
        ----------
        (str): The input string without HTML tags
        """

        compiled = re.compile(r"<.*?>")
        clean_text = re.sub(compiled, "", text)

        return clean_text

    async def request_anilist(
        self, interaction: discord.Interaction, query: str, variables: dict, key: str
    ) -> tuple[dict, str] | tuple[None, None]:
        """
        Makes a request to the Anilist API

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        query (str): The GraphQL query
        variables (str): The variables for the query
        key (str): The key to return from the response

        Returns
        ----------
        (tuple[dict, str] | tuple[None, None]): The response from the Anilist API
        """

        try:
            url = "https://graphql.anilist.co"
            response = requests.post(url, json={"query": query, "variables": variables}, timeout=10)
            response = response.json()
            data = response["data"][key]
            url = data["siteUrl"]
        except TypeError:
            embed = embed_templates.error_fatal("Kunne ikke finne det du søkte etter!")
            await interaction.response.send_message(embed=embed)
            return None, None

        return data, url

    def construct_favorite_media_string(self, media: list) -> str:
        """
        Constructs a string with the user's favorite media

        Parameters
        ----------
        media (list): The list of media returned from the Anilist API

        Returns
        ----------
        (str): The constructed string
        """

        favorite_media = []
        for node in media:
            try:
                nsfwtag = "🔞" if node["isAdult"] else ""
                anime_name = node["title"]["romaji"]
                anime_url = node["siteUrl"]
                favorite_media.append(f"* [{anime_name}]({anime_url}){nsfwtag}")
            except KeyError:
                pass

        return "\n".join(favorite_media)

    def construct_favorite_entity_string(self, entities: list, studio: bool = False) -> str:
        """
        Constructs a string with the user's favorite entities

        Parameters
        ----------
        entities (list): The list of entities returned from the Anilist API
        studio (bool): Whether the entities are studios or not

        Returns
        ----------
        (str): The constructed string
        """

        favortie_entities = []
        for entity in entities:
            try:
                if studio:
                    entity_name = entity["name"]
                else:
                    entity_name = entity["name"]["full"]
                entity_url = entity["siteUrl"]
                favortie_entities.append(f"* [{entity_name}]({entity_url})")
            except KeyError:
                pass

        return "\n".join(favortie_entities)

    def construct_release_schedule_string(self, numbers: dict) -> str:
        """
        Constructs a string with the media's release schedule

        Parameters
        ----------
        numbers (dict): dict containing release date and end date

        Returns
        ----------
        (str): The constructed string
        """

        # Release and end date formatting
        if numbers["start_day"] != "?" and numbers["start_month"] != "?" and numbers["start_year"] != "?":
            release_date = datetime(numbers["start_year"], numbers["start_month"], numbers["start_day"])
            release_date = discord.utils.format_dt(release_date, style="d")
        else:
            release_date = f'{numbers["start_day"]}.{numbers["start_month"]}.{numbers["start_year"]}'

        if numbers["end_day"] != "?" and numbers["end_month"] != "?" and numbers["end_year"] != "?":
            end_date = datetime(numbers["end_year"], numbers["end_month"], numbers["end_day"])
            end_date = discord.utils.format_dt(end_date, style="d")
        else:
            end_date = f'{numbers["end_day"]}.{numbers["end_month"]}.{numbers["end_year"]}'

        if release_date == end_date:
            date = release_date
        else:
            date = f"{release_date} - {end_date}"

        return date

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 5)
    @anilist_profile.command(name="generelt", description="Viser informasjon om en Anilistprofil")
    async def anilist_profile_general(self, interaction: discord.Interaction, bruker: str):
        """
        Shows general information about a user's Anilist profile

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        bruker (str): The user to get information about
        """

        #  GraphQL
        query = """
        query ($name: String) {
            User (name: $name) {
                name
                siteUrl
                avatar {
                    large
                }
                options {
                    profileColor
                }
                statistics {
                    anime {
                        minutesWatched
                        statuses {
                            count
                            status
                        }
                    }
                    manga {
                        chaptersRead
                        statuses {
                            count
                            status
                        }
                    }
                }
                favourites {
                    anime (perPage: 3) {
                        nodes {
                            isAdult
                            title {
                                romaji
                            }
                            siteUrl
                        }
                    }
                    manga (perPage: 3) {
                            nodes {
                            isAdult
                            title {
                                romaji
                            }
                            siteUrl
                        }
                    }
                    studios (perPage: 3) {
                        nodes {
                            name
                            siteUrl
                        }
                    }
                    characters (perPage: 3) {
                        nodes {
                            name {
                                full
                            }
                            siteUrl
                        }
                    }
                    staff (perPage: 3) {
                        nodes {
                            name {
                                full
                            }
                            siteUrl
                        }
                    }
                }
            }
        }
        """
        variables = {"name": bruker}
        data, url = await self.request_anilist(interaction, query, variables, "User")

        if not data:
            return

        user_name = data["name"]
        profile_pic = data["avatar"]["large"]
        days_watched = round(data["statistics"]["anime"]["minutesWatched"] / 1440, 1)
        chapters_read = data["statistics"]["manga"]["chaptersRead"]
        color = self.convert_color(data["options"]["profileColor"])

        anime_statuses = {
            status["status"]: {"count": status["count"]} for status in data["statistics"]["anime"]["statuses"]
        }
        manga_statuses = {
            status["status"]: {"count": status["count"]} for status in data["statistics"]["manga"]["statuses"]
        }

        try:
            anime_completed = anime_statuses["COMPLETED"]["count"]
        except KeyError:
            anime_completed = 0
        try:
            manga_completed = manga_statuses["COMPLETED"]["count"]
        except KeyError:
            manga_completed = 0

        favourite_anime = self.construct_favorite_media_string(data["favourites"]["anime"]["nodes"])
        favourite_manga = self.construct_favorite_media_string(data["favourites"]["manga"]["nodes"])
        favourite_character = self.construct_favorite_entity_string(data["favourites"]["characters"]["nodes"])
        favourite_staff = self.construct_favorite_entity_string(data["favourites"]["staff"]["nodes"])
        favourite_studio = self.construct_favorite_entity_string(data["favourites"]["studios"]["nodes"], studio=True)

        embed = discord.Embed(title=user_name, color=color, url=url)
        embed.set_author(name="Anilist", icon_url=self.anilist_logo)
        embed.set_thumbnail(url=profile_pic)
        embed.add_field(name="Antall dager sett", value=days_watched)
        embed.add_field(name="Antall anime sett", value=anime_completed)
        embed.add_field(name="Antall kapitler lest", value=chapters_read)
        embed.add_field(name="Antall manga lest", value=manga_completed)
        if favourite_anime:
            embed.add_field(name="Noen favorittanime", value=favourite_anime, inline=False)
        if favourite_manga:
            embed.add_field(name="Noen favorittmanga", value=favourite_manga, inline=False)
        if favourite_character:
            embed.add_field(name="Noen favorittkarakterer", value=favourite_character, inline=False)
        if favourite_studio:
            embed.add_field(name="Noen favorittstudioer", value=favourite_studio, inline=False)
        if favourite_staff:
            embed.add_field(name="Noen favorittskapere", value=favourite_staff, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 5)
    @anilist_profile.command(name="anime", description="Se statistikk om animetittingen til en bruker")
    async def anilist_profile_anime_stats(self, interaction: discord.Interaction, bruker: str):
        """
        Shows anime viewing statistics from a user's Anilist profile

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        bruker (str): The user to get information about
        """

        #  GraphQL
        query = """
        query ($name: String) {
            User (name: $name) {
                name
                siteUrl
                avatar {
                    large
                }
                options {
                    profileColor
                }
                statistics {
                    anime {
                        minutesWatched
                        episodesWatched
                        meanScore
                        statuses {
                            count
                            status
                            minutesWatched
                        }
                        studios (limit: 3, sort: COUNT_DESC) {
                            studio {
                                name
                                siteUrl
                            }
                        }
                        genres (limit: 3, sort: COUNT_DESC) {
                            genre
                        }
                    }
                }
            }
        }
        """
        variables = {"name": bruker}
        data, url = await self.request_anilist(interaction, query, variables, "User")

        if not data:
            return

        user_name = data["name"]
        profile_pic = data["avatar"]["large"]
        days_watched = round(data["statistics"]["anime"]["minutesWatched"] / 1440, 1)
        episodes_watched = data["statistics"]["anime"]["episodesWatched"]
        color = self.convert_color(data["options"]["profileColor"])

        statuses = {
            status["status"]: {"count": status["count"], "minutes": status["minutesWatched"]}
            for status in data["statistics"]["anime"]["statuses"]
        }

        try:
            completed = statuses["COMPLETED"]["count"]
        except KeyError:
            completed = 0
        try:
            watching = statuses["CURRENT"]["count"]
        except KeyError:
            watching = 0
        try:
            planning = statuses["PLANNING"]["count"]
            planning_days = round(statuses["PLANNING"]["minutes"] / 1440, 1)
        except KeyError:
            planning = 0
            planning_days = 0
        try:
            dropped = statuses["DROPPED"]["count"]
        except KeyError:
            dropped = 0

        anime_mean_score = data["statistics"]["anime"]["meanScore"]
        if not anime_mean_score:
            anime_mean_score = "**Ingen**"

        most_watched_genres = ", ".join([genre["genre"] for genre in data["statistics"]["anime"]["genres"]])
        most_watched_studios = self.construct_favorite_entity_string(data["statistics"]["anime"]["studios"])

        embed = discord.Embed(title=user_name, color=color, url=url)
        embed.set_author(name="Anilist", icon_url=self.anilist_logo)
        embed.set_thumbnail(url=profile_pic)
        embed.add_field(name="Gj.snittsvurdering gitt", value=anime_mean_score)
        embed.add_field(name="Antall dager sett", value=days_watched)
        embed.add_field(name="Antall episoder sett", value=episodes_watched)
        embed.add_field(name="Antall anime sett", value=completed)
        embed.add_field(name="Ser på nå", value=watching)
        embed.add_field(name="Planlegger å se", value=f"{planning}\n({planning_days} dager)")
        embed.add_field(name="Droppet", value=dropped)
        if most_watched_genres:
            embed.add_field(name="Mest sette sjangere", value=most_watched_genres, inline=False)
        if most_watched_studios:
            embed.add_field(name="Mest sette studioer", value=most_watched_studios, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 5)
    @anilist_profile.command(name="manga", description="Se statistikk om mangalesingen til en bruker")
    async def anilist_profile_manga_stats(self, interaction: discord.Interaction, bruker: str):
        """
        Shows manga reading statistics from a user's Anilist profile

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        bruker (str): The user to get information about
        """

        #  GraphQL
        query = """
        query ($name: String) {
            User(name: $name) {
                name
                siteUrl
                avatar {
                    large
                }
                options {
                    profileColor
                }
                statistics {
                    manga {
                        chaptersRead
                        volumesRead
                        meanScore
                        statuses {
                            count
                            status
                            chaptersRead
                        }
                        staff (limit: 3, sort: COUNT_DESC) {
                            staff {
                                name {
                                    full
                                }
                                siteUrl
                            }
                        }
                        genres (limit: 3, sort: COUNT_DESC) {
                            genre
                        }
                    }
                }
            }
        }
        """
        variables = {"name": bruker}
        data, url = await self.request_anilist(interaction, query, variables, "User")

        if not data:
            return

        user_name = data["name"]
        profile_pic = data["avatar"]["large"]
        chapters_read = round(data["statistics"]["manga"]["chaptersRead"] / 1440, 1)
        volumes_read = data["statistics"]["manga"]["volumesRead"]
        color = self.convert_color(data["options"]["profileColor"])

        statuses = {
            status["status"]: {"count": status["count"], "chapters": status["chaptersRead"]}
            for status in data["statistics"]["manga"]["statuses"]
        }

        try:
            completed = statuses["COMPLETED"]["count"]
        except KeyError:
            completed = 0
        try:
            reading = statuses["CURRENT"]["count"]
        except KeyError:
            reading = 0
        try:
            planning = statuses["PLANNING"]["count"]
            planning_chapters = statuses["PLANNING"]["chapters"]
        except KeyError:
            planning = 0
            planning_chapters = 0
        try:
            dropped = statuses["DROPPED"]["count"]
        except KeyError:
            dropped = 0

        manga_mean_score = data["statistics"]["manga"]["meanScore"]
        if manga_mean_score == 0:
            manga_mean_score = "**Ingen**"

        most_read_genres = ", ".join([genre["genre"] for genre in data["statistics"]["manga"]["genres"]])
        most_read_staff = self.construct_favorite_entity_string(data["statistics"]["manga"]["staff"])

        embed = discord.Embed(title=user_name, color=color, url=url)
        embed.set_author(name="Anilist", icon_url=self.anilist_logo)
        embed.set_thumbnail(url=profile_pic)
        embed.add_field(name="Gj.snittsvurdering gitt", value=manga_mean_score)
        embed.add_field(name="Antall kapitler lest", value=chapters_read)
        embed.add_field(name="Antall volum lest", value=volumes_read)
        embed.add_field(name="Antall manga lest", value=completed)
        embed.add_field(name="Leser nå", value=reading)
        embed.add_field(name="Planlegger å lese", value=f"{planning}\n({planning_chapters} kapitler)")
        embed.add_field(name="Droppet", value=dropped)
        if most_read_genres:
            embed.add_field(name="Mest leste sjangere", value=most_read_genres, inline=False)
        if most_read_staff:
            embed.add_field(name="Mest leste skapere", value=most_read_staff, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 5)
    @anilist.command(name="anime", description="Hent informasjon om en anime")
    async def anilist_anime(self, interaction: discord.Interaction, navn: str):
        """
        Shows information about an anime

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        navn (str): The name of the anime to fetch information about
        """

        #  GraphQL
        query = """
        query ($search: String, $isMain: Boolean) {
            Media (search: $search, type: ANIME) {
                siteUrl
                format
                status
                description (asHtml: false)
                episodes
                duration
                genres
                isAdult
                bannerImage
                meanScore
                coverImage {
                    large
                    color
                }
                startDate {
                    year
                    month
                    day
                }
                endDate {
                    year
                    month
                    day
                }
                title {
                    romaji
                    english
                    native
                }
                studios (isMain: $isMain) {
                    nodes {
                        name
                        siteUrl
                    }
                }
                staff (sort: ROLE) {
                    edges {
                        role
                        node {
                            siteUrl
                            name {
                                first
                                last
                                native
                            }
                        }
                    }
                }
            }
        }
        """
        variables = {"search": navn, "isMain": True}
        data, url = await self.request_anilist(interaction, query, variables, "Media")

        if not data:
            return

        nsfw = data["isAdult"]
        if nsfw:
            embed = embed_templates.error_warning(
                "Animen du søkte på er NSFW. Gjør kommandoen i en NSFW-kanal i stedet"
            )
            return await interaction.response.send_message(embed=embed)

        cover_image = data["coverImage"]["large"]
        banner_image = data["bannerImage"]
        mean_score = data["meanScore"]

        color = self.convert_color(data["coverImage"]["color"])

        title_romaji = data["title"]["romaji"]
        title_native = data["title"]["native"]
        title_english = data["title"]["english"]
        titles = [title_romaji, title_native, title_english]
        title_romaji, title_native, title_english = [title if title else "" for title in titles]

        description = self.remove_html(data["description"]) if data["description"] else ""
        genres = ", ".join(data["genres"])
        studios_string = self.construct_favorite_entity_string(data["studios"]["nodes"], studio=True)

        staff = data["staff"]["edges"]
        director_string = ""
        for staff_member in staff:
            if staff_member["role"] == "Director":
                director_first_name = staff_member["node"]["name"]["first"]
                director_last_name = staff_member["node"]["name"]["last"]
                director_native_name = staff_member["node"]["name"]["native"]
                director_url = staff_member["node"]["siteUrl"]
                director_string += (
                    f"[{director_first_name} {director_last_name} " + f"({director_native_name})]({director_url})"
                )

        episodes = data["episodes"]
        duration = data["duration"]

        numbers = {
            "episodes": episodes,
            "duration": duration,
            "start_day": data["startDate"].get("day") if data["startDate"].get("day") else "?",
            "start_month": data["startDate"].get("month") if data["startDate"].get("month") else "?",
            "start_year": data["startDate"].get("year") if data["startDate"].get("year") else "?",
            "end_day": data["endDate"].get("day") if data["endDate"].get("day") else "?",
            "end_month": data["endDate"].get("month") if data["endDate"].get("month") else "?",
            "end_year": data["endDate"].get("year") if data["endDate"].get("year") else "?",
        }

        date = self.construct_release_schedule_string(numbers)

        length_string = ""
        if numbers["duration"] == 1:
            length_string += "minutt "
        else:
            length_string += "minutter "
        if numbers["episodes"] == 1:
            length_string += "lang"
        else:
            length_string += "lange"

        # Status
        status = data["status"]
        status = self.convert_status(status)

        # Format
        media_format = data["format"]
        media_format = self.convert_media_format(media_format)

        embed = discord.Embed(color=color, title=title_romaji, url=url, description=f"{title_native}\n{title_english}")
        embed.set_thumbnail(url=cover_image)
        embed.add_field(name="Format", value=media_format)
        embed.add_field(name="Status", value=status)
        if studios_string:
            embed.add_field(name="Studio", value=studios_string)
        if director_string:
            embed.add_field(name="Regissør", value=director_string)
        embed.add_field(name="Utgivelsesdato", value=date)
        if media_format == "Film":
            embed.add_field(name="Lengde", value=f"{duration} minutter")
        else:
            embed.add_field(name="Episoder", value=f"{episodes} ({duration} {length_string})")
        if mean_score:
            embed.add_field(name="Gj.snittsvurdering", value=f"{mean_score}/100")
        embed.add_field(name="Sjangere", value=genres)
        if len(description) < 1024 and description:
            embed.add_field(name="Sammendrag", value=description, inline=False)
        if banner_image:
            embed.set_image(url=banner_image)
        await interaction.response.send_message(embed=embed)

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 5)
    @anilist.command(name="manga", description="Hent informasjon om en manga")
    async def anilist_manga(self, interaction: discord.Interaction, navn: str):
        """
        Shows information about a manga

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        navn (str): The name of the manga to fetch information about
        """

        query = """
            query ($search: String) {
                Media (search: $search, type: MANGA) {
                    siteUrl
                    format
                    status
                    description (asHtml: false)
                    volumes
                    chapters
                    genres
                    isAdult
                    bannerImage
                    meanScore
                    coverImage {
                        large
                        color
                    }
                    startDate {
                        year
                        month
                        day
                    }
                    endDate {
                        year
                        month
                        day
                    }
                    title {
                        romaji
                        english
                        native
                    }
                    staff(sort: ROLE) {
                        edges {
                            role
                            node {
                                siteUrl
                                name {
                                    first
                                    last
                                    native
                                }
                            }
                        }
                    }
                }
            }
            """
        variables = {"search": navn}
        data, url = await self.request_anilist(interaction, query, variables, "Media")

        if not data:
            return

        nsfw = data["isAdult"]
        if nsfw:
            embed = embed_templates.error_warning(
                "Mangaen du søkte på er NSFW. Gjør kommandoen i en NSFW-kanal i stedet"
            )
            return await interaction.response.send_message(embed=embed)

        cover_image = data["coverImage"]["large"]
        banner_image = data["bannerImage"]
        mean_score = data["meanScore"]

        color = self.convert_color(data["coverImage"]["color"])

        title_romaji = data["title"]["romaji"]
        title_native = data["title"]["native"]
        title_english = data["title"]["english"]
        titles = [title_romaji, title_native, title_english]
        title_romaji, title_native, title_english = [title if title else "" for title in titles]

        description = self.remove_html(data["description"]) if data.get("description") else ""
        genres = ", ".join(data["genres"])

        staff = data["staff"]["edges"]
        staff_string = ""
        for staff_member in staff:
            staff_first_name = staff_member["node"]["name"]["first"]
            staff_last_name = staff_member["node"]["name"]["last"]
            staff_native_name = staff_member["node"]["name"]["native"]
            staff_url = staff_member["node"]["siteUrl"]
            staff_string += f"[{staff_first_name} {staff_last_name} ({staff_native_name})]({staff_url})\n"

        numbers = {
            "chapters": data["chapters"],
            "volumes": data["volumes"],
            "start_day": data["startDate"].get("day") if data["startDate"].get("day") else "?",
            "start_month": data["startDate"].get("month") if data["startDate"].get("month") else "?",
            "start_year": data["startDate"].get("year") if data["startDate"].get("year") else "?",
            "end_day": data["endDate"].get("day") if data["endDate"].get("day") else "?",
            "end_month": data["endDate"].get("month") if data["endDate"].get("month") else "?",
            "end_year": data["endDate"].get("year") if data["endDate"].get("year") else "?",
        }
        date = self.construct_release_schedule_string(numbers)

        chapters_string = ""
        if numbers["chapters"] == 1:
            chapters_string += "kapittel"
        else:
            chapters_string += "kapitler"

        status = data["status"]
        status = self.convert_status(status)

        media_format = data["format"]
        media_format = self.convert_media_format(media_format)

        embed = discord.Embed(color=color, title=title_romaji, url=url, description=f"{title_native}\n{title_english}")
        embed.set_thumbnail(url=cover_image)
        embed.add_field(name="Format", value=media_format)
        embed.add_field(name="Status", value=status)
        if staff_string:
            embed.add_field(name="Laget av", value=staff_string)
        embed.add_field(name="Utgivelsesdato", value=date)
        embed.add_field(name="Lengde", value=f'{numbers["chapters"]} {chapters_string}\n{numbers["volumes"]} volum')
        if mean_score:
            embed.add_field(name="Gj.snittsvurdering", value=f"{mean_score}/100")
        embed.add_field(name="Sjangere", value=genres)
        if len(description) < 1024 and description:
            embed.add_field(name="Sammendrag", value=description, inline=False)
        if banner_image:
            embed.set_image(url=banner_image)
        await interaction.response.send_message(embed=embed)

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 5)
    @anilist.command(name="karakter", description="Hent informasjon om en karakter")
    async def anilist_character(self, interaction: discord.Interaction, navn: str):
        """
        Shows information about a character

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        navn (str): The name of the character to fetch information about
        """

        query = """
            query ($search: String) {
                Character (search: $search) {
                    name {
                        full
                        native
                    }
                    siteUrl
                    favourites
                    image {
                        large
                    }
                    description (asHtml: false)
                    media (sort: POPULARITY_DESC, perPage: 1) {
                        edges {
                            node {
                                siteUrl
                                isAdult
                                title {
                                    romaji
                                }
                            }
                            characterRole
                            voiceActors {
                                siteUrl
                                language
                                name {
                                    full
                                    native
                                }
                            }
                        }
                    }
                }
            }
            """
        variables = {"search": navn}
        data, url = await self.request_anilist(interaction, query, variables, "Character")

        if not data:
            return

        name_romaji = data["name"]["full"]
        name_native = data["name"]["native"]
        image = data["image"]["large"]
        favourites = data["favourites"]

        if data["description"]:
            description = self.remove_html(data["description"])
            if len(description) > 1024:
                description = description[0:1020] + "..."
        else:
            description = "*Ingen biografi funnet* 😔"

        featured_in = []
        voice_actors = []
        for media in data["media"]["edges"]:
            nsfwtag = "🔞" if media["node"]["isAdult"] else ""
            media_name = media["node"]["title"]["romaji"]
            media_url = media["node"]["siteUrl"]
            media_role = self.onvert_role_names(media["characterRole"])
            for voice_actor in media["voiceActors"]:
                voice_actor_url = voice_actor["siteUrl"]
                voice_actor_language = self.convert_language_names(voice_actor["language"])
                voice_actor_name = voice_actor["name"]["full"]
                if voice_actor["name"]["native"] != " " and voice_actor["name"]["native"] is not None:
                    voice_actor_name += f' ({voice_actor["name"]["native"]}'
                voice_actors.append(f"\t* {voice_actor_language} stemme: [{voice_actor_name}]({voice_actor_url})")

            voice_actors_string = "\n".join(voice_actors)
            featured_in.append(f"* [{media_name}]({media_url}){nsfwtag} som {media_role}\n{voice_actors_string}")

        featured_in = "\n\n".join(featured_in)

        embed = discord.Embed(color=0x02A9FF, title=name_romaji, url=url, description=name_native)
        embed.set_thumbnail(url=image)
        embed.add_field(name="Antall favoritter på Anilist", value=favourites, inline=False)
        embed.add_field(name="Biografi", value=description, inline=False)
        embed.add_field(name="Er med i bl.a.", value=featured_in, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 5)
    @anilist.command(name="skaper", description="Hent informasjon om en skaper")
    async def anilist_creator(self, interaction: discord.Interaction, navn: str):
        """
        Shows information about a creator

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        navn (str): The name of the creator to fetch information about
        """

        query = """
            query ($search: String) {
                Staff(search: $search) {
                    name {
                        full
                        native
                    }
                    siteUrl
                    image {
                        large
                    }
                    language
                    favourites
                    description(asHtml: false)
                    staffMedia(sort: POPULARITY_DESC, perPage: 2) {
                        edges {
                            staffRole
                            node {
                                siteUrl
                                isAdult
                                title {
                                    romaji
                                }
                            }
                        }
                    }
                    characters(sort: FAVOURITES_DESC, perPage: 2) {
                        edges {
                            node {
                                name {
                                    full
                                    native
                                }
                                siteUrl
                            }
                        }
                    }
                }
            }
            """
        variables = {"search": navn}
        data, url = await self.request_anilist(interaction, query, variables, "Staff")

        if not data:
            return

        name_romaji = data["name"]["full"]
        name_native = data["name"]["native"]
        image = data["image"]["large"]
        favourites = data["favourites"]

        if data["description"]:
            description = self.remove_html(data["description"])
            if len(description) > 1024:
                description = description[0:1020] + "..."
        else:
            description = "*Ingen biografi funnet* 😔"

        featured_in = []
        for media in data["staffMedia"]["edges"]:
            nsfwtag = "🔞" if media["node"]["isAdult"] else ""
            media_name = media["node"]["title"]["romaji"]
            media_url = media["node"]["siteUrl"]
            media_role = media["staffRole"]
            featured_in.append(f"* [{media_name}]({media_url}){nsfwtag}\n{media_role}")
        featured_in = "\n".join(featured_in)

        characters = []
        for character in data["characters"]["edges"]:
            character_url = character["node"]["siteUrl"]
            character_name = character["node"]["name"]["full"]
            if character["node"]["name"]["native"] != " " and character["node"]["name"]["native"] is not None:
                character_name += f' ({character["node"]["name"]["native"]}'
            characters.append(f"* [{character_name}]({character_url})")
        characters = "\n".join(characters)

        embed = discord.Embed(color=0x02A9FF, title=name_romaji, url=url, description=name_native)
        embed.set_thumbnail(url=image)
        embed.add_field(name="Antall favoritter på Anilist", value=favourites, inline=False)
        embed.add_field(name="Biografi", value=description, inline=False)
        if characters:
            embed.add_field(name="Har vært stemmen til bl.a.", value=characters, inline=False)
        if featured_in:
            embed.add_field(name="Har deltatt i produksjonen av bl.a.", value=featured_in, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 5)
    @anilist.command(name="studio", description="Hent informasjon om et studio")
    async def anilist_studio(self, interaction: discord.Interaction, navn: str):
        """
        Shows information about a studio

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        navn (str): The name of the studio to fetch information about
        """

        query = """
            query ($search: String) {
                Studio(search: $search) {
                    name
                    siteUrl
                    favourites
                    media(sort: POPULARITY_DESC, perPage: 3) {
                    nodes {
                        siteUrl
                        coverImage {
                            large
                        }
                        isAdult
                        title {
                        romaji
                        }
                    }
                    }
                }
                }
            """
        variables = {"search": navn}
        data, url = await self.request_anilist(interaction, query, variables, "Studio")

        if not data:
            return

        name = data["name"]
        favourites = data["favourites"]

        popular_media = []
        for media in data["media"]["nodes"]:
            nsfwtag = "🔞" if media["isAdult"] else ""
            media_name = media["title"]["romaji"]
            media_url = media["siteUrl"]
            popular_media.append(f"- [{media_name}]({media_url}){nsfwtag}")
        popular_media = "\n".join(popular_media)

        query2 = """
            query ($search: String) {
                Studio(search: $search) {
                    media(sort: START_DATE_DESC) {
                    nodes {
                        siteUrl
                        status
                        isAdult
                        title {
                        romaji
                        }
                    }
                    }
                }
                }
            """
        data = requests.post(
            "https://graphql.anilist.co", json={"query": query2, "variables": variables}, timeout=10
        ).json()
        data = data["data"]["Studio"]

        recent_media = []
        upcoming_media = []
        for media in data["media"]["nodes"]:
            nsfwtag = "🔞" if media["isAdult"] else ""
            media_name = media["title"]["romaji"]
            media_url = media["siteUrl"]
            if media["status"] == "NOT_YET_RELEASED":
                upcoming_media.append(f"- [{media_name}]({media_url}){nsfwtag}")
            else:
                recent_media.append(f"- [{media_name}]({media_url}){nsfwtag}")
        recent_media = "\n".join(recent_media[0:3])
        upcoming_media = "\n".join(upcoming_media[0:3])

        embed = discord.Embed(color=0x02A9FF, title=name, url=url)
        embed.add_field(name="Antall favoritter på Anilist", value=favourites, inline=False)
        if popular_media:
            embed.add_field(name="Mest Populære Anime", value=popular_media, inline=False)
        if recent_media:
            embed.add_field(name="Nyeste Utgitte Anime", value=recent_media, inline=False)
        if upcoming_media:
            embed.add_field(name="Kommende Anime", value=upcoming_media, inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(Anime(bot))
