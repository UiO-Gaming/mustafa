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
import psycopg2
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks
from nltk.corpus import stopwords
from PIL import Image
from psycopg2.extras import execute_batch
from wordcloud import WordCloud as WCloud  # Avoid naming conflicts with cog class name

from cogs.utils import embed_templates

# from wordcloud import ImageColorGenerator


class WordCloud(commands.Cog):
    """Generate a wordcloud based on the most frequent words posted"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot
        self.cursor = self.bot.db_connection.cursor()
        self.init_db()

        # Default dict where all users are empty defaultdicts
        # The user's defaultdict has a default value of 0
        self.word_freq_cache = defaultdict(lambda: defaultdict(int))

        self.consenting_users = []
        self.populate_consenting_users()

        nltk.download("stopwords")

        self.batch_update_word_freqs_loop.start()

    def init_db(self):
        """
        Create the necessary tables for the Ordsky cog to work
        """

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS wordcloud_metadata (
                discord_user_id BIGINT PRIMARY KEY,
                tracked_since_message_channel_id BIGINT NOT NULL,
                tracked_since_message_id BIGINT NOT NULL UNIQUE
            )
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS wordcloud_words (
                discord_user_id BIGINT NOT NULL,
                word TEXT NOT NULL,
                frequency INTEGER NOT NULL,
                PRIMARY KEY (discord_user_id, word)
            )
            """
        )

    async def cog_unload(self):
        """
        Insert cache to db, stop tasks and close the database connection on cog unload
        """

        await self.batch_update_word_freqs()
        self.batch_update_word_freqs_loop.cancel()
        self.cursor.close()

    def populate_consenting_users(self):
        """
        Populates the cached list of consenting users
        """

        self.cursor.execute(
            """
            SELECT discord_user_id
            FROM wordcloud_metadata
            """
        )
        self.consenting_users = [row[0] for row in self.cursor.fetchall()]

    async def batch_update_word_freqs(self):
        """
        Inserts cached word frequencies into the database.
        We do this in order to prevent excess database writes
        """

        if not self.word_freq_cache:
            return

        # Flatten the defaultdict into a list of tuples
        # This is a bit of a hack but it works
        word_freqs = list(
            itertools.chain.from_iterable(
                [(user_id, word, freq) for word, freq in user_word_freqs.items()]
                for user_id, user_word_freqs in self.word_freq_cache.items()
            )
        )

        # Insert cache into database
        try:
            execute_batch(
                self.cursor,
                """
                INSERT INTO wordcloud_words (discord_user_id, word, frequency)
                VALUES (%s, %s, %s)
                ON CONFLICT (discord_user_id, word)
                DO UPDATE SET frequency = wordcloud_words.frequency + EXCLUDED.frequency
                """,
                word_freqs,
            )
        except psycopg2.Error as err:
            self.bot.db_connection.rollback()
            self.bot.logger.error(f"Failed to insert wordcloud cache into database - {err}")

        self.word_freq_cache.clear()

    @tasks.loop(minutes=20)
    async def batch_update_word_freqs_loop(self):
        """
        Clears and inserts word frequency cache into the database every 20 minutes
        """

        self.bot.logger.info("Dumping word cloud cache to database...")
        await self.batch_update_word_freqs()

    @commands.Cog.listener("on_message")
    async def word_freq_listener(self, message: discord.Message):
        """
        Listens for all messages of consenting users

        Parameters
        ----------
        message (discord.Message): Message to count
        """

        if message.author.id not in self.consenting_users:
            return

        # Ignore bot commands
        # This is a very naive approach but it works for our use case
        if not message.clean_content[:2].isalpha():
            return

        # Divide into words
        # Also very naive but luckily we only speak norwegian and english :)
        words = message.clean_content.split(" ")

        for word in words:
            # Filter urls
            # do I really need to comment on this being naive again?
            if re.match(r"https?://", word):
                continue

            # Remove punctuation
            word = word.lower().strip("/+-=~|$%@#*_.,;:!?()[]{}<>\"'`\n")
            if not word:
                continue

            # Enter into cache
            # This may take a performance hit but who tf cares. We're using python anyway
            self.word_freq_cache[message.author.id][word] += 1

    @staticmethod
    def generate_wordcloud(text: str, max_words: int = 4000, allow_bigrams: bool = False) -> BytesIO:
        """
        Generates a wordcloud

        Parameters
        ----------
        text (str): Text to generate wordcloud from
        max_words (int): Maximum number of words to include in the wordcloud. Defaults to 4000
        allow_bigrams (bool): Whether to allow bigrams in the wordcloud. Defaults to False

        Returns
        ----------
        BytesIO: BytesIO object containing the wordcloud image
        """

        filter_words = set(stopwords.words("norwegian") + stopwords.words("english"))
        mask = np.array(Image.open("./src/assets/word_cloud_mask.png"))

        wc = WCloud(
            max_words=max_words,
            mask=mask,
            repeat=False,
            stopwords=filter_words,
            min_word_length=3,
            collocations=allow_bigrams,
        )
        wc.process_text(text)
        wc.generate(text)

        # Color the wordcloud based on the mask
        # wc.recolor(color_func=ImageColorGenerator(mask))

        img = wc.to_image()
        b = BytesIO()
        img.save(b, "png")
        b.seek(0)
        return b

    wordcloud_group = app_commands.Group(
        name="ordsky", description="Generer en ordsky basert på dine mest frekvente sagte ord"
    )
    wordcloud_generate_group = app_commands.Group(
        parent=wordcloud_group, name="generer", description="Generer en ordsky basert på dine mest frekvente sagte ord"
    )

    @app_commands.checks.bot_has_permissions(embed_links=True)
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
            self.cursor.execute(
                """
                INSERT INTO wordcloud_metadata
                VALUES (%s, %s, %s)
                """,
                (interaction.user.id, interaction.channel_id, interaction.id),
            )
        except psycopg2.Error as err:
            self.bot.db_connection.rollback()
            self.bot.logger.error(f"Failed to insert wordcloud metadata into database - {err}")
            return await interaction.response.send_message(
                embed=embed_templates.error_fatal("Klarte ikke å skrive til database"),
                ephemeral=False,
            )

        self.consenting_users.append(interaction.user.id)

        embed = embed_templates.success(interaction, "Samtykke registrert!")
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.checks.bot_has_permissions(embed_links=True)
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

        self.word_freq_cache.pop(f"{interaction.user.id}", None)

        try:
            self.cursor.execute(
                """
                DELETE FROM wordcloud_metadata WHERE discord_user_id = %s;
                DELETE FROM wordcloud_words WHERE discord_user_id = %s;
                """,
                (interaction.user.id, interaction.user.id),
            )
        except psycopg2.Error as err:
            self.bot.db_connection.rollback()
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

        self.cursor.execute(
            """
            SELECT word, frequency
            FROM wordcloud_words
            WHERE discord_user_id = %s
            ORDER BY frequency DESC
            """,
            (interaction.user.id,),
        )
        result = self.cursor.fetchall()

        if not result:
            return await interaction.response.send_message(
                embed=embed_templates.error_warning(self.MSG_NO_DATA), ephemeral=False
            )

        freq_list = {f"{word}": freq for word, freq in result}

        embed = discord.Embed(description="Her er dataen jeg har lagret om deg")
        buffer = StringIO()
        buffer.write(json.dumps(freq_list, indent=4))
        buffer.seek(0)
        file = discord.File(buffer, filename=f"uiog_word_freqs_{interaction.user.id}.json")
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
        await self.batch_update_word_freqs()

        # Fetch word count from database
        self.cursor.execute(
            """
            SELECT word, frequency
            FROM wordcloud_words
            WHERE discord_user_id = %s
            """,
            (interaction.user.id,),
        )
        results = self.cursor.fetchall()

        if not results:
            return await interaction.followup.send(
                embed=embed_templates.error_warning(self.MSG_NO_DATA), ephemeral=False
            )

        # Fetch tracking start time metadata
        self.cursor.execute(
            """
            SELECT tracked_since_message_channel_id, tracked_since_message_id
            FROM wordcloud_metadata
            WHERE discord_user_id = %s
            """,
            (interaction.user.id,),
        )
        origin_msg_channel_id, origin_msg_id = self.cursor.fetchone()
        try:
            origin_msg_channel = self.bot.get_channel(origin_msg_channel_id)
            origin_msg = await origin_msg_channel.fetch_message(origin_msg_id)
            origin_msg_timestamp = discord.utils.format_dt(origin_msg.created_at, style="f")
        except discord.errors.NotFound:
            origin_found = False
        else:
            origin_found = True

        # Converts the raw SQL results tuple to a string where
        # each word occurs the x number of frequency that is provided
        # Having to reconstruct the data this way is probably not optimal
        text = " ".join(list(itertools.chain(*([word] * count for (word, count) in results))))

        # Generate word cloud
        generation_task = functools.partial(WordCloud.generate_wordcloud, text)
        word_cloud = await self.bot.loop.run_in_executor(None, generation_task)

        word_cloud_file = discord.File(word_cloud, filename=f"wordcloud_{interaction.user.id}.png")
        embed = discord.Embed(title="☁️ Her er ordskyen din! ☁️")
        if origin_found:
            embed.description = (
                f"Basert på de 4000 mest frekvente ordene dine siden {origin_msg_timestamp}\n"
                + f"[Se melding]({origin_msg.jump_url})"
            )
        else:
            embed.description = "Basert på de 4000 mest frekvente ordene dine siden `ukjent dato`"
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
        member_role = interaction.guild.get_role(779849617651138601)

        # Fetch last 1000 messages
        all_messages = ""
        for channel in interaction.guild.text_channels:
            if not channel.permissions_for(interaction.user).send_messages:
                continue

            # Avoid reading secret board member chats
            if (
                not channel.permissions_for(member_role).send_messages
                and not channel.permissions_for(interaction.guild.default_role).send_messages
            ):
                continue

            try:
                async for message in channel.history(
                    limit=int(antall / 2)
                ):  # Limit search in each channel to half of requested
                    if message.author != interaction.user:
                        continue

                    # Filter bot command messages
                    if not message.clean_content[:2].isalpha():
                        continue

                    # Filter URLs
                    filtered_msg = re.sub(
                        r"https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)",  # noqa: E501
                        "",
                        message.clean_content,
                    )

                    all_messages += f"{filtered_msg} "
            except discord.errors.Forbidden:
                continue

        if not all_messages:
            return await interaction.followup.send(
                embed=embed_templates.error_warning(interaction, text="Fant ingen data om deg"), ephemeral=False
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
