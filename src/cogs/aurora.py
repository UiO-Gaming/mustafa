from datetime import datetime
from datetime import timedelta
from zoneinfo import ZoneInfo

import discord
import requests
from discord.ext import commands
from discord.ext import tasks


class Aurora(commands.Cog):
    """Aurora Borealis forecasts and alerts"""

    def __init__(self, bot: commands.Bot):
        """
        Parameters
        ----------
        bot (commands.Bot): The bot instance
        """

        self.bot = bot

        self.notified = datetime(2000, 9, 11)  # Used to prevent spamming aurora alerts
        self.aurora_alarm.start()
        self.AURORA_CHANNEL = 747542544291987599

    def cog_unload(self):
        self.bot.logger.info("Unloading cog")
        self.aurora_alarm.cancel()

    async def get_forecast(self) -> dict | None:
        """
        Get the current aurora and cloud cover forecast for Chateau Neuf

        Returns
        -------
        (dict) The forecast data | None
        """

        data = requests.get("https://www.yr.no/api/v0/locations/1-72837/auroraforecast?language=nb").json()
        if not data or data["status"]["code"] != "Ok":
            self.bot.logger.warning("Failed to get forecast data")
            return None

        valid_sightings = []
        for interval in data["shortIntervals"]:
            # Convert to datetime objects, convert timezone to utc and strip timezone info
            start = datetime.fromisoformat(interval["start"]).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

            # If sighting is not in within the next 12 hours ignore
            if (start - datetime.now()) > timedelta(hours=12):
                continue

            if (
                interval["sunlight"]["id"] == "night"
                and interval["kpIndex"] >= 5
                and interval["cloudCover"]["value"] < 50
                and interval["auroraValue"] > 0.5
            ):
                valid_sightings.append(interval)

        if not valid_sightings:
            return None

        most_likely_sighting = max(valid_sightings, key=lambda x: x["auroraValue"])
        return most_likely_sighting

    @tasks.loop(minutes=60)
    async def aurora_alarm(self):
        """
        Checks if the aurora forecast is above 50% and sends a message to the aurora channel if it is
        """

        await self.bot.wait_until_ready()  # Make sure we can fetch the #general channel

        if datetime.now() - self.notified < timedelta(hours=12):
            self.bot.logger.info(
                "aurora_alarm: Not sending aurora alert because it has been less than 12 hours since last alert"
            )
            return

        if not (forecast := await self.get_forecast()):
            self.bot.logger.info("aurora_alarm: Fetch forecast")
            return

        channel = self.bot.get_channel(self.AURORA_CHANNEL)
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
        self.notified = datetime.now()  # Update the last notification time


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(Aurora(bot))
