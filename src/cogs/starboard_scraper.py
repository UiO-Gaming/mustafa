import re

import discord
import psycopg2
from discord.ext import commands
from discord.ext import tasks

from cogs.utils import misc_utils


class StarboardScraper(commands.Cog):
    """
    Saves starboard messages to the db for other services.
    We would make our lives 10x easier by hosting r. danny ourselves
    but alas it's too late for that now :(
    """

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot
        self.starboard_channel_id = 757614289812193280

        self.cursor = self.bot.db_connection.cursor()
        self.init_db()
        self.star_check.start()

    def init_db(self):
        """
        Create the necessary tables for the cog to work
        """

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS starboard_messages (
                id SERIAL PRIMARY KEY,
                starboard_message_id BIGINT UNIQUE,
                original_message_id BIGINT,
                original_channel_id BIGINT
            )
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS starboard_scraper_state (
                id INTEGER PRIMARY KEY DEFAULT 1,
                last_scraped_message_id BIGINT,
                last_scrape_time TIMESTAMP,
                CHECK (id = 1)
            )
            """
        )

    def get_last_scraped_message_id(self):
        """
        Get the ID of the last scraped message

        Returns
        -------
        int or None: Last scraped message ID or None if never scraped
        """
        self.cursor.execute(
            """
            SELECT last_scraped_message_id
            FROM starboard_scraper_state
            WHERE id = 1
            """
        )
        result = self.cursor.fetchone()
        return result[0] if result else None

    def update_last_scraped_message_id(self, message_id: int):
        """
        Update the last scraped message ID

        Parameters
        ----------
        message_id (int): The message ID to store
        """
        self.cursor.execute(
            """
            INSERT INTO starboard_scraper_state (id, last_scraped_message_id, last_scrape_time)
            VALUES (1, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO UPDATE SET
                last_scraped_message_id = EXCLUDED.last_scraped_message_id,
                last_scrape_time = CURRENT_TIMESTAMP
            """,
            (message_id,),
        )
        self.bot.db_connection.commit()

    def parse_starboard_message(self, message: discord.Message):
        """
        Parse a starboard message to extract original message IDs.

        Parameters
        ----------
        message (discord.Message): The starboard message to parse

        Returns
        -------
        tuple(int, int) | None: (original_message_id, original_channel_id) or None if parsing failed
        """

        if not message.embeds:
            return None

        embed = message.embeds[0]

        for field in embed.fields:
            if field.name == "Original":
                link_match = re.search(r"https://discord\.com/channels/\d+/(\d+)/(\d+)", field.value)
                if link_match:
                    original_channel_id = int(link_match.group(1))
                    original_message_id = int(link_match.group(2))
                    return (original_message_id, original_channel_id)

        return None

    async def scrape_starboard_channel(self):
        """
        Scrape all messages from the starboard channel and save IDs to database
        """

        guild = self.bot.get_guild(self.bot.guild_id)
        if not guild:
            self.bot.logger.error(f"Could not find guild with ID {self.bot.guild_id}")
            return

        starboard_channel = guild.get_channel(self.starboard_channel_id)
        if not starboard_channel:
            self.bot.logger.error(f"Could not find starboard channel {self.starboard_channel_id}")
            return

        last_scraped_id = self.get_last_scraped_message_id()

        if last_scraped_id:
            self.bot.logger.info(f"Resuming scrape from msg ID {last_scraped_id}")
        else:
            self.bot.logger.info("Starting starboard scrape...")

        new_count = 0
        error_count = 0
        latest_message_id = None

        try:
            async for message in starboard_channel.history(
                limit=None, oldest_first=False, after=discord.Object(id=last_scraped_id) if last_scraped_id else None
            ):
                if not latest_message_id:
                    latest_message_id = message.id

                if not message.author.bot or not message.embeds:
                    continue

                parsed_ids = self.parse_starboard_message(message)
                if not parsed_ids:
                    error_count += 1
                    continue

                original_message_id, original_channel_id = parsed_ids

                try:
                    self.cursor.execute(
                        """
                        INSERT INTO starboard_messages
                        (starboard_message_id, original_message_id, original_channel_id)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (starboard_message_id) DO NOTHING
                        """,
                        (message.id, original_message_id, original_channel_id),
                    )

                    if self.cursor.rowcount > 0:
                        new_count += 1

                except psycopg2.Error as e:
                    self.bot.logger.error(f"Database error for message {message.id}: {e}")
                    error_count += 1
                    continue

            if latest_message_id:
                self.update_last_scraped_message_id(latest_message_id)

            self.bot.logger.info(f"Starboard scrape complete: {new_count} new messages, {error_count} errors")

        except discord.errors.Forbidden:
            self.bot.logger.error("Missing permissions to read starboard channel")
        except Exception as e:
            self.bot.logger.error(f"Error during starboard scrape: {e}")

    @tasks.loop(time=misc_utils.MIDNIGHT)
    async def star_check(self):
        """
        Update DB with latest starboard data
        """

        self.bot.logger.info("Waiting for bot to be ready")
        await self.bot.wait_until_ready()
        await self.scrape_starboard_channel()

    async def cog_unload(self):
        self.bot.logger.info("Unloading cog")
        self.star_check().cancel()
        self.cursor.close()


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(StarboardScraper(bot))
