import asyncio
import json
from zoneinfo import ZoneInfo

import discord
import requests
from discord.ext import commands


class WebsiteEvents(commands.Cog):
    """Uploads Discord events to Sanity CMS"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot
        self.auth_header = {
            "Authorization": f"Bearer {self.bot.sanity['api_token']}",
            "Content-Type": "application/json",
        }
        self.api_url = (
            f"https://{self.bot.sanity['project_id']}.api.sanity.io"
            + f"/v2021-03-25/data/mutate/{self.bot.sanity['dataset']}"
        )

    async def cog_load(self):
        asyncio.create_task(self.after_ready())

    async def after_ready(self):
        """
        Wait for the bot's cache to be ready before syncing events
        """

        self.bot.logger.info("Waiting for bot to be ready")
        await self.bot.wait_until_ready()
        self.bot.logger.info("Ready")
        await self.sync_events()

    async def sync_events(self):
        """
        Sync events from Discord to Sanity CMS
        """

        self.bot.logger.info("Syncing events to Sanity CMS")

        guild = self.bot.get_guild(self.bot.guild_id)

        for event in guild.scheduled_events:
            if event.status == discord.EventStatus.cancelled:
                await self.delete_event(event)
            elif event.status == discord.EventStatus.scheduled:
                await self.create_event(event)

        self.bot.logger.info("Finished syncing events! Note errors may have occured")

    @commands.Cog.listener("on_scheduled_event_create")
    async def create_event(self, event: discord.ScheduledEvent):
        """
        Creates an event in Sanity CMS when an event is added on Discord

        Parameters
        ----------
        event (discord.ScheduledEvent): The created event
        """

        # Convert timezone to Europe/Oslo
        # We need to set a timezone unit before being able to convert it to another timezone
        # That's why this line is so fucking weird
        time = event.start_time.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Oslo"))

        document = {
            "_type": "event",
            "_id": str(event.id),
            "slug": {"_type": "slug", "current": str(event.id)},
            "title": event.name,
            "date": time.strftime("%Y-%m-%d %H:%M"),
            "location": event.location,
            "description": event.description,
        }

        mutation = {
            "mutations": [
                {
                    "createOrReplace": document,
                }
            ]
        }

        response = requests.post(self.api_url, headers=self.auth_header, data=json.dumps(mutation))
        if response.status_code == 200:
            self.bot.logger.info(f"Created Event in Sanity with ID: {event.id}")
        else:
            self.bot.logger.error(f"Failed to create event in Sanity with ID: {event.id}. Response: {response.text}")

    @commands.Cog.listener("on_scheduled_event_delete")
    async def delete_event(self, event: discord.ScheduledEvent):
        """
        Deletes an event in Sanity CMS when an event is deleted on Discord

        Parameters
        ----------
        event (discord.ScheduledEvent): The deleted event
        """

        mutation = {"mutations": [{"delete": {"id": str(event.id)}}]}

        response = requests.post(self.api_url, headers=self.auth_header, data=json.dumps(mutation))
        if response.status_code == 200:
            self.bot.logger.info(f"Deleted Event in Sanity with ID: {event.id}")
        else:
            self.bot.logger.error(f"Failed to delete event in Sanity with ID: {event.id}. Response: {response.text}")

    @commands.Cog.listener("on_scheduled_event_update")
    async def update_event(self, before: discord.ScheduledEvent, after: discord.ScheduledEvent):
        """
        Updates an event in Sanity when edited on discord

        Parameters
        ----------
        before (discord.ScheduledEvent): The event before editing
        after (discord.ScheduleEvent): The new event
        """

        if before.id != after.id:
            # This might be redundant as events aren't supposed to change its id
            # However for some odd reason it seems to be the case with recurring events
            # As all events have the same id up until around 48 hours before its start time
            # I have not looked into this though
            await self.delete_event(before)
            await self.create_event(after)
        else:
            await self.create_event(after)


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(WebsiteEvents(bot))
