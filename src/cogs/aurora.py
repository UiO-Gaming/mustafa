from datetime import datetime
from datetime import timedelta
from datetime import timezone

import discord
from discord.ext import commands
from discord.ext import tasks

from cogs.utils import misc_utils


class Aurora(commands.Cog):
    """Aurora Borealis forecasts and alerts"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot

        self.notified = datetime(2000, 9, 11, tzinfo=timezone.utc)  # Used to prevent spamming aurora alerts
        self.aurora_alarm.start()

    def cog_unload(self):
        """
        Stop the aurora alarm when the cog is unloaded
        """

        self.bot.logger.info("Unloading cog")
        self.aurora_alarm.cancel()

    async def get_forecast(self) -> dict | None:
        """
        Get the current aurora and cloud cover forecast for Chateau Neuf

        Returns
        ----------
        (dict | None): The forecast data. None if it couldn't be fetched
        """

        async with self.bot.http_session.get(
            "https://www.yr.no/api/v0/locations/1-72837/auroraforecast?language=nb"
        ) as response:
            data = await response.json(content_type=None)
        try:
            if not data or data["status"]["code"] != "Ok":
                self.bot.logger.warning("Failed to get forecast data")
                return None

            now = discord.utils.utcnow()
            valid_sightings = []
            for interval in data["shortIntervals"]:
                start = datetime.fromisoformat(interval["start"])
                end = datetime.fromisoformat(interval["end"])

                # Ignore sightings that have already ended or are more than 12 hours away
                if end <= now or start - now > timedelta(hours=12):
                    continue

                if (
                    interval["sunlight"]["id"] == "night"
                    and interval["kpIndex"] >= 5
                    and interval["cloudCover"]["value"] < 50
                    and interval["auroraValue"] > 0.5
                ):
                    valid_sightings.append(interval)
        except (KeyError, TypeError, ValueError) as e:
            self.bot.logger.warning(f"Unexpected forecast data format: {e!r}")
            return None

        if not valid_sightings:
            return None

        most_likely_sighting = max(valid_sightings, key=lambda x: x["auroraValue"])
        return most_likely_sighting

    @tasks.loop(minutes=60)
    @misc_utils.log_errors
    async def aurora_alarm(self):
        """
        Checks if the aurora forecast is above 50% and sends a message to the aurora channel if it is
        """

        await self.bot.wait_until_ready()  # Make sure we can fetch the #general channel

        if discord.utils.utcnow() - self.notified < timedelta(hours=12):
            self.bot.logger.info(
                "aurora_alarm: Not sending aurora alert because it has been less than 12 hours since last alert"
            )
            return

        if not (forecast := await self.get_forecast()):
            self.bot.logger.info("aurora_alarm: Fetch forecast")
            return

        channel = self.bot.get_channel(self.bot.channel_ids.get("aurora"))
        if not channel:
            self.bot.logger.warning("aurora_alarm: Failed to get aurora channel")
            return

        try:
            start = discord.utils.format_dt(datetime.fromisoformat(forecast["start"]), style="t")
        except ValueError as e:
            self.bot.logger.warning(e)
            start = f"`{forecast['start']}`"

        try:
            end = discord.utils.format_dt(datetime.fromisoformat(forecast["end"]), style="t")
        except ValueError as e:
            self.bot.logger.warning(e)
            end = f"`{forecast['end']}`"

        embed = discord.Embed(
            title="Nordlysvarsel",
            description=f"### Størst sjanse mellom {start} og {end}",
            color=discord.Color.purple(),
        )
        embed.add_field(name="Sjanse for Nordlys", value=f"{round(forecast['auroraValue'] * 100)}%", inline=False)
        embed.add_field(name="KP-Indeks", value=forecast["kpIndex"])
        embed.add_field(name="Skydekke", value=f"{forecast['cloudCover']['value']}%")
        await channel.send(
            content="SJANSE FOR NORDLYS AKKURAT NÅ PÅ NEUF! Se ut vinduet istedenfor på den dumme skjermen din",
            embed=embed,
        )
        self.notified = discord.utils.utcnow()  # Update the last notification time


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): The bot instance
    """

    await bot.add_cog(Aurora(bot))
