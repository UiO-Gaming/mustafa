import functools
import itertools
import json
import re
from collections import defaultdict
from io import BytesIO
from io import StringIO

import discord
import nltk
import numpy as np
import psycopg
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks
from nltk.corpus import stopwords
from PIL import Image
from wordcloud import WordCloud as WCloud  # Avoid naming conflicts with cog class name

from cogs.utils import embed_templates
from cogs.utils import misc_utils


class WordCloud(commands.Cog):
    """Generate a wordcloud based on the most frequent words posted"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot

        # Default dict where all users are empty defaultdicts
        # The user's defaultdict has a default value of 0
        self.word_freq_cache = defaultdict(lambda: defaultdict(int))

        # We cache the consenting users to avoid querying the database every 16:36
        # It's frail but it works unless you have a skill issue
        self.consenting_users = []

        try:
            nltk.data.find("corpora/stopwords")
        except LookupError:
            nltk.download("stopwords")

        self.MSG_NO_DATA = "Fant ingen data om deg"  # SonarCloud recommended this LMAO. Makes sense but also not

    async def cog_load(self):
        """
        Set up the database before the cog is used
        """

        await self.init_db()
        await self.populate_consenting_users()
        self.insert_cache_loop.start()

    async def init_db(self):
        """
        Create the necessary tables for the Ordsky cog to work
        """

        await self.bot.db.execute("""
            CREATE TABLE IF NOT EXISTS wordcloud_metadata (
                discord_user_id BIGINT PRIMARY KEY,
                tracked_since_message_channel_id BIGINT NOT NULL,
                tracked_since_message_id BIGINT NOT NULL UNIQUE
            )
            """)
        await self.bot.db.execute("""
            CREATE TABLE IF NOT EXISTS wordcloud_words (
                discord_user_id BIGINT NOT NULL,
                word TEXT NOT NULL,
                frequency INTEGER NOT NULL,
                PRIMARY KEY (discord_user_id, word)
            )
            """)

    async def cog_unload(self):
        """
        Insert cache to db, stop tasks and close the database connection on cog unload
        """

        self.bot.logger.info("Unloading cog")
        self.insert_cache_loop.cancel()
        await self.insert_cache()

    async def populate_consenting_users(self):
        """
        Populates the cached list of consenting users
        """

        rows = await self.bot.db.fetchall("""
            SELECT discord_user_id
            FROM wordcloud_metadata
            """)
        self.consenting_users = [row[0] for row in rows]

    async def insert_cache(self):
        """
        Inserts cached word frequencies into the database.
        We do this in order to prevent excess database writes
        """

        if not self.word_freq_cache:
            return

        # Swap in an empty cache before awaiting, so words from messages sent in the meantime aren't lost
        cache, self.word_freq_cache = self.word_freq_cache, defaultdict(lambda: defaultdict(int))

        # Flatten the defaultdict into a list of tuples
        # This is a bit of a hack but it works
        word_freqs = list(
            itertools.chain.from_iterable(
                [(user_id, word, freq) for word, freq in user_word_freqs.items()]
                for user_id, user_word_freqs in cache.items()
            )
        )

        # Insert cache into database
        try:
            await self.bot.db.executemany(
                """
                INSERT INTO wordcloud_words (discord_user_id, word, frequency)
                VALUES (%s, %s, %s)
                ON CONFLICT (discord_user_id, word)
                DO UPDATE SET frequency = wordcloud_words.frequency + EXCLUDED.frequency
                """,
                word_freqs,
            )
        except psycopg.Error as err:
            self.bot.logger.error(f"Failed to insert wordcloud cache into database - {err}")

    @tasks.loop(minutes=20)
    @misc_utils.log_errors
    async def insert_cache_loop(self):
        """
        Clears and inserts word frequency cache into the database every 20 minutes
        """

        self.bot.logger.info("Dumping word cloud cache to database...")
        await self.insert_cache()

    @commands.Cog.listener("on_message")
    async def word_freq_listener(self, message: discord.Message):
        """
        Listens for all messages of consenting users

        Parameters
        ----------
        message (discord.Message): Message to count
        """

        if not self.can_count_message(message):
            return

        tokens = self.tokenize(message.clean_content)

        for token in tokens:
            # Enter into cache
            # This may take a performance hit but who tf cares. We're using python anyway
            self.word_freq_cache[message.author.id][token] += 1

    def can_count_message(self, message: discord.Message) -> bool:
        """
        Check if a message can be counted

        Parameters
        ----------
        message (discord.Message): Message to check

        Returns
        ----------
        bool: Whether the message can be counted
        """

        return (
            message.author.id in self.consenting_users
            and message.clean_content[:2].isalpha()  # Naive check for traditional bot commands
        )

    def tokenize(self, text: str) -> list[str]:
        """
        Tokenize a text into words

        Parameters
        ----------
        text (str): Text to tokenize

        Returns
        ----------
        list[str]: List of words
        """

        tokens = []

        # Divide into words
        # Very naive but luckily we only speak norwegian and english :)
        words = text.split(" ")

        for word in words:
            # Filter urls
            # do I really need to comment on this being naive again?
            if re.match(r"https?://", word):
                continue

            # Remove punctuation
            word = word.lower().strip("/+-=~|$%@#*_.,;:!?()[]{}<>\"'`\n")
            if not word:
                continue

            tokens.append(word)

        return tokens

    MIN_WORD_LENGTH = 3

    @staticmethod
    def filter_words() -> set[str]:
        """
        Returns
        ----------
        set[str]: Norwegian and english words too common to include in a wordcloud
        """

        return set(stopwords.words("norwegian") + stopwords.words("english"))

    @staticmethod
    def render_wordcloud(max_words: int, allow_bigrams: bool, generate: callable) -> BytesIO:
        """
        Creates a wordcloud, fills it using the given function and renders it to a PNG

        Parameters
        ----------
        max_words (int): Maximum number of words to include in the wordcloud
        allow_bigrams (bool): Whether to allow bigrams in the wordcloud
        generate (callable): Function that takes the WordCloud object and fills it with words

        Returns
        ----------
        BytesIO: BytesIO object containing the wordcloud image
        """

        mask = np.array(Image.open("./src/assets/word_cloud_mask.png"))
        wc = WCloud(
            max_words=max_words,
            mask=mask,
            repeat=False,
            stopwords=WordCloud.filter_words(),
            min_word_length=WordCloud.MIN_WORD_LENGTH,
            collocations=allow_bigrams,
        )
        generate(wc)

        b = BytesIO()
        wc.to_image().save(b, "png")
        b.seek(0)
        return b

    @staticmethod
    def generate_wordcloud(text: str, max_words: int = 4000, allow_bigrams: bool = False) -> BytesIO:
        """
        Generates a wordcloud from text

        Parameters
        ----------
        text (str): Text to generate wordcloud from
        max_words (int): Maximum number of words to include in the wordcloud. Defaults to 4000
        allow_bigrams (bool): Whether to allow bigrams in the wordcloud. Defaults to False

        Returns
        ----------
        BytesIO: BytesIO object containing the wordcloud image
        """

        return WordCloud.render_wordcloud(max_words, allow_bigrams, lambda wc: wc.generate(text))

    @staticmethod
    def generate_wordcloud_from_frequencies(frequencies: dict[str, int], max_words: int = 4000) -> BytesIO:
        """
        Generates a wordcloud from word frequencies, applying the same filtering as for text

        Parameters
        ----------
        frequencies (dict[str, int]): How many times each word has been used
        max_words (int): Maximum number of words to include in the wordcloud. Defaults to 4000

        Returns
        ----------
        BytesIO: BytesIO object containing the wordcloud image
        """

        filter_words = WordCloud.filter_words()
        frequencies = {
            word: count
            for word, count in frequencies.items()
            if len(word) >= WordCloud.MIN_WORD_LENGTH and word not in filter_words and not word.isdigit()
        }
        return WordCloud.render_wordcloud(max_words, False, lambda wc: wc.generate_from_frequencies(frequencies))

    wordcloud_group = app_commands.Group(
        name="ordsky", description="Generer en ordsky basert på dine mest frekvente sagte ord"
    )
    wordcloud_generate_group = app_commands.Group(
        parent=wordcloud_group, name="generer", description="Generer en ordsky basert på dine mest frekvente sagte ord"
    )

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @wordcloud_group.command(name="samtykke", description="Gi samtykke til å samle meldingsdataen din for ordskyer")
    async def consent(self, interaction: discord.Interaction):
        """
        Gi samtykke til å samle meldingsdataen din

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        if interaction.user.id in self.consenting_users:
            return await interaction.response.send_message(
                embed=embed_templates.error_warning("Du har allerede samtykket"), ephemeral=False
            )

        try:
            await self.bot.db.execute(
                """
                INSERT INTO wordcloud_metadata
                VALUES (%s, %s, %s)
                """,
                (interaction.user.id, interaction.channel_id, interaction.id),
            )
        except psycopg.Error as err:
            self.bot.logger.error(f"Failed to insert wordcloud metadata into database - {err}")
            return await interaction.response.send_message(
                embed=embed_templates.error_fatal("Klarte ikke å skrive til database"),
                ephemeral=False,
            )

        self.consenting_users.append(interaction.user.id)

        embed = embed_templates.success("Samtykke registrert!")
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @wordcloud_group.command(name="slett", description="Fjern samtykke og slett alle dine ordskydata")
    async def consent_remove(self, interaction: discord.Interaction):
        """
        Fjern samtykke og slett meldingsdata

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        try:
            self.consenting_users.remove(interaction.user.id)
        except ValueError:
            return await interaction.response.send_message(
                embed=embed_templates.error_warning(self.MSG_NO_DATA), ephemeral=False
            )

        self.word_freq_cache.pop(interaction.user.id, None)

        try:
            await self.bot.db.execute_in_transaction(
                [
                    ("DELETE FROM wordcloud_metadata WHERE discord_user_id = %s", (interaction.user.id,)),
                    ("DELETE FROM wordcloud_words WHERE discord_user_id = %s", (interaction.user.id,)),
                ]
            )
        except psycopg.Error as err:
            self.bot.logger.error(f"Failed to delete wordcloud metadata from database - {err}")
            return await interaction.response.send_message(
                embed=embed_templates.error_fatal("Klarte ikke å slette fra database"),
                ephemeral=False,
            )

        embed = embed_templates.success("Meldingsdata er slettet!")
        await interaction.response.send_message(embed=embed)

    @app_commands.checks.bot_has_permissions(embed_links=True, attach_files=True)
    @app_commands.checks.cooldown(1, 10)
    @wordcloud_group.command(name="data", description="Få tilsendt dine ordskydata i JSON-format")
    async def data(self, interaction: discord.Interaction):
        """
        Få tilsendt dine data

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        result = await self.bot.db.fetchall(
            """
            SELECT word, frequency
            FROM wordcloud_words
            WHERE discord_user_id = %s
            ORDER BY frequency DESC
            """,
            (interaction.user.id,),
        )

        if not result:
            return await interaction.response.send_message(
                embed=embed_templates.error_warning(self.MSG_NO_DATA), ephemeral=False
            )

        freq_list = {f"{word}": freq for word, freq in result}

        # Create Json file
        buffer = StringIO()
        buffer.write(json.dumps(freq_list, indent=4))
        buffer.seek(0)
        file = discord.File(buffer, filename=f"uiog_word_freqs_{interaction.user.id}.json")

        embed = discord.Embed(description="Her er dataen jeg har lagret om deg")
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

    @app_commands.checks.bot_has_permissions(embed_links=True, attach_files=True)
    @app_commands.checks.cooldown(1, 10)
    @wordcloud_generate_group.command(
        name="alle", description="Generer en ordsky basert på dine mest frekvente sagte ord siden du ga samtykke"
    )
    async def generate_db(self, interaction: discord.Interaction):
        """
        Generer en ordsky basert på dine mest frekvente sagte ord siden du ga samtykke

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        await interaction.response.defer()

        # Clear cache first to ensure correct count
        await self.insert_cache()

        # Fetch word count from database
        results = await self.bot.db.fetchall(
            """
            SELECT word, frequency
            FROM wordcloud_words
            WHERE discord_user_id = %s
            """,
            (interaction.user.id,),
        )

        if not results:
            return await interaction.followup.send(
                embed=embed_templates.error_warning(self.MSG_NO_DATA), ephemeral=False
            )

        # The stored "message" ID is the ID of the consent interaction, so its timestamp is when tracking started
        row = await self.bot.db.fetchone(
            """
            SELECT tracked_since_message_id
            FROM wordcloud_metadata
            WHERE discord_user_id = %s
            """,
            (interaction.user.id,),
        )
        tracked_since = discord.utils.snowflake_time(row[0])

        generation_task = functools.partial(WordCloud.generate_wordcloud_from_frequencies, dict(results))
        word_cloud = await self.bot.loop.run_in_executor(None, generation_task)

        word_cloud_file = discord.File(word_cloud, filename=f"wordcloud_{interaction.user.id}.png")
        embed = discord.Embed(title="☁️ Her er ordskyen din! ☁️")
        embed.description = (
            f"Basert på de 4000 mest frekvente ordene dine siden {discord.utils.format_dt(tracked_since, style='f')}"
        )
        embed.set_image(url=f"attachment://wordcloud_{interaction.user.id}.png")
        await interaction.followup.send(embed=embed, file=word_cloud_file)

    @app_commands.checks.bot_has_permissions(embed_links=True, attach_files=True)
    @app_commands.checks.cooldown(1, 30)
    @wordcloud_generate_group.command(
        name="siste",
        description="Generer en ordsky basert på dine mest frekvente sagte ord fra de siste meldingene dine",
    )
    async def generate_last(self, interaction: discord.Interaction, antall: app_commands.Range[int, 100, 2000] = 1000):
        """
        Generer en ordsky basert på dine mest frekvente sagte ord fra de siste meldingene dine

        Parameters
        ----------
        interaction (discord.Interaction): Slash command context object
        """

        await interaction.response.defer()

        # Get member role for future channel permission checking
        board_member_role = interaction.guild.get_role(self.bot.role_ids.get("board_member"))

        # This is horrible but there's a lot of edge cases to handle so spare me pls
        all_messages = ""
        for channel in interaction.guild.text_channels:
            if not channel.permissions_for(interaction.user).send_messages:
                continue

            # Avoid reading secret board member chats
            if (
                board_member_role  # None if invoked outside of UiO Gaming's server. Avoiding crash due to AND check
                and not channel.permissions_for(board_member_role).send_messages
                and not channel.permissions_for(interaction.guild.default_role).send_messages
            ):
                continue

            try:
                # Limit search to half of requested messages to avoid rate limits
                # We assume we can still fetch enough tokens to reach the requested amount
                async for message in channel.history(limit=int(antall / 2)):
                    if message.author.id != interaction.user.id or not self.can_count_message(message):
                        continue

                    filtered_msg = " ".join(self.tokenize(message.clean_content))
                    all_messages += f"{filtered_msg} "
            except discord.errors.Forbidden:
                continue

        if not all_messages:
            return await interaction.followup.send(
                embed=embed_templates.error_warning(self.MSG_NO_DATA), ephemeral=False
            )

        # Generate word cloud
        generation_task = functools.partial(
            WordCloud.generate_wordcloud, all_messages, max_words=1000, allow_bigrams=True
        )
        word_cloud = await self.bot.loop.run_in_executor(None, generation_task)

        word_cloud_file = discord.File(word_cloud, filename=f"wordcloud_{interaction.user.id}.png")
        embed = discord.Embed(title="☁️ Her er ordskyen din! ☁️")
        embed.description = (
            f"Basert på de {int(antall/2)} siste meldingene i alle kanaler og "
            + f"topp {antall} mest frekvente ord i dine meldinger"
        )
        embed.set_image(url=f"attachment://wordcloud_{interaction.user.id}.png")
        await interaction.followup.send(embed=embed, file=word_cloud_file)


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(WordCloud(bot))
