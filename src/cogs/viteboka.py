import aiohttp
import discord
import pypandoc
import regex
from discord import app_commands
from discord.ext import commands

from cogs.utils import embed_templates

WIKI_BASE_URL = "https://viteboka.studentersamfundet.no"
API_URL = f"{WIKI_BASE_URL}/w/api.php"


async def fetch_article(session: aiohttp.ClientSession, title: str):
    """
    Fetch an article from Viteboka

    Parameters
    ----------
    session (aiohttp.ClientSession): The HTTP session to use
    title (str): The title of the article to fetch

    Returns
    ----------
    tuple: The title, url, text and image of the article
    """

    params = {
        "action": "parse",
        "format": "json",
        "page": title,
        "prop": "text|images|displaytitle|wikitext",
    }

    async with session.get(API_URL, params=params) as response:
        if response.status != 200:
            raise VitebokaException("Klarte ikke å nå API")
        page = await response.json(content_type=None)
    if not (parse := page.get("parse")):
        raise VitebokaException(
            "Fant ingen artikkel med det navnet. Kan hende den finnes, men wiki-søk er balle. De burde tatt søketek"
        )

    title = parse.get("title")
    url = f"{WIKI_BASE_URL}/?curid={parse.get('pageid')}"
    image = f"{WIKI_BASE_URL}/w/images/{parse.get('images')[0]}" if parse.get("images") else None
    text = parse.get("wikitext")["*"]

    # If you're reading this, know that I'm on my way
    # to your house right now to erase your memories of ever reading this shit.
    # Parsing text fucking sucks. Even more so when it's wiki text with no consistencies whatsoever
    # This is wildly inefficent but I don't. fucking. care. Just make it work
    text = regex.sub(
        r"(?=\{)(\{([^{}]|(?1))*\})|\[\[(Kategori|Fil):.+?\]\]|\{.+?\}", "", text, flags=regex.MULTILINE | regex.DOTALL
    )  # Remove templates, categories and images
    text = pypandoc.convert_text(text, "markdown", format="mediawiki")
    text = regex.sub(
        r"\[(.+?)\]\(.+? \"wikilink\"\)", r"\1", text, flags=regex.MULTILINE | regex.DOTALL
    )  # Pandoc adds alt text to links. discord doesn't support that
    text = regex.sub(r"\{.+\}", "", text)  # Pandoc adds section links. Remove them
    text = text.strip("\n")
    text = text[:1000] + "..." if len(text) > 1000 else text

    return title, url, text, image


def viteboka_embed(title: str, url: str, text: str, image: str):
    """
    Template for viteoka article embeds

    Parameters
    ----------
    title (str): The title of the article
    url (str): The url of the article
    text (str): The text of the article
    image (str): The url of the image of the article

    Returns
    ----------
    discord.Embed: The embed
    """

    embed = discord.Embed(color=discord.Color.orange(), title=title, url=url, description=text)
    embed.set_author(name="Viteboka (Beta)", icon_url="https://viteboka.studentersamfundet.no/w/images/Emblem.png")
    if image:
        embed.set_image(url=image)
    return embed


class VitebokaException(Exception):
    pass


class Viteboka(commands.Cog):
    """Query viteboka for information"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot

    viteboka_group = app_commands.Group(name="viteboka", description="Søk i Viteboka etter informasjon")

    @app_commands.checks.bot_has_permissions(embed_links=True, attach_files=True)
    @app_commands.checks.cooldown(1, 10)
    @viteboka_group.command(name="søk", description="Søk etter en artikkel i Viteboka")
    @app_commands.rename(query="søkestreng")
    @app_commands.describe(query="Det du vil søke etter")
    async def search(self, interaction: discord.Interaction, query: str):
        """
        Search for an article in Viteboka

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        query (str): The search query
        """

        await interaction.response.defer()

        params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": query,
        }
        async with self.bot.http_session.get(API_URL, params=params) as response:
            if response.status != 200:
                self.bot.logger.error(f"Failed to search for articles with query {query}: {response.status}")
                embed = embed_templates.error_fatal("Klarte ikke å søke etter artikler")
                return await interaction.followup.send(embed=embed)
            data = await response.json(content_type=None)
        search_results = data["query"]["search"]

        if not search_results:
            self.bot.logger.info(f"No articles found with query {query}")
            embed = embed_templates.error_warning("Fant ingen artikler som matcher søket")
            return await interaction.followup.send(embed=embed)

        if len(search_results) == 1:
            title = search_results[0]["title"]
        else:
            view = discord.ui.View()
            for i, result in enumerate(search_results[:5]):
                view.add_item(ArticleButton(interaction.user, str(i + 1), result["title"]))

            embed = discord.Embed(title="Velg en artikkel")
            embed.description = "\n".join(
                [f"**{i+1}.** {result['title']}" for i, result in enumerate(search_results[:5])]
            )
            embed.description += "\n\nFinner du ikke det du leter etter? Synd! Jeg orker ikke å implementere pagination"
            return await interaction.followup.send(embed=embed, view=view)

        try:
            title, url, text, image = await fetch_article(self.bot.http_session, title)
        except VitebokaException as e:
            self.bot.logger.error(f"Failed to fetch article {title}: {e}")
            embed = embed_templates.error_fatal(str(e))
            return await interaction.followup.send(embed=embed)

        embed = viteboka_embed(title, url, text, image)
        await interaction.followup.send(embed=embed)

    @app_commands.checks.bot_has_permissions(embed_links=True, attach_files=True)
    @app_commands.checks.cooldown(1, 5)
    @viteboka_group.command(name="tilfeldig", description="Få en tilfeldig artikkel fra Viteboka")
    async def random(self, interaction: discord.Interaction):
        """
        Fetch a random article from Viteboka

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        await interaction.response.defer()

        params = {
            "action": "query",
            "format": "json",
            "list": "random",
            "rnnamespace": 0,  # Main namespace
            "rnlimit": 1,  # Get one random article
        }

        async with self.bot.http_session.get(API_URL, params=params) as response:
            if response.status != 200:
                self.bot.logger.error(f"Failed to fetch random article: {response.status}")
                embed = embed_templates.error_fatal("Klarte ikke å søke etter en tilfeldig artikkel")
                return await interaction.followup.send(embed=embed)
            data = await response.json(content_type=None)
        random_article_title = data["query"]["random"][0]["title"]

        try:
            title, url, text, image = await fetch_article(self.bot.http_session, random_article_title)
        except VitebokaException as e:
            self.bot.logger.error(f"Failed to fetch article {random_article_title}: {e}")
            embed = embed_templates.error_fatal(str(e))
            return await interaction.followup.send(embed=embed)

        embed = viteboka_embed(title, url, text, image)
        await interaction.followup.send(embed=embed)


class ArticleButton(discord.ui.Button):
    """Button for selecting an article from a list of search results"""

    def __init__(
        self,
        owner: discord.User | discord.Member,
        label: str,
        article_title: str,
    ):
        """
        Parameters
        -----------
        owner (discord.User|discord.Member): The user that invoked the paginator. Only this user can use the button
        label (str): The label of the button
        article_title (str): The title of the article the button is associated with
        """

        super().__init__(label=label)
        self.owner = owner
        self.article_title = article_title

    async def callback(self, interaction: discord.Interaction):
        """
        What to do when the button is pressed

        Parameters
        -----------
        interaction (discord.Interaction): Slash command context object
        """

        await interaction.response.defer()

        if interaction.user.id != self.owner.id:
            return await interaction.followup.send(
                "Bare den som skrev kommandoen kan bruke denne knappen", ephemeral=True
            )

        try:
            title, url, text, image = await fetch_article(interaction.client.http_session, self.article_title)
        except VitebokaException as e:
            embed = embed_templates.error_fatal(str(e))
            return await interaction.followup.send(embed=embed)
        else:
            embed = viteboka_embed(title, url, text, image)
            await interaction.message.edit(embed=embed, view=None)


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(Viteboka(bot))
