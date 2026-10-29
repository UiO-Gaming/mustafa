import asyncio
import datetime
import functools
import subprocess
import textwrap
from dataclasses import dataclass
from math import ceil

import aiohttp
import cv2
import discord
import numpy as np
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

# Midnight in the bot's time zone. run.py sets it before loading the cogs
MIDNIGHT = datetime.time(tzinfo=datetime.UTC)


def localize(dt: datetime.datetime, tz: datetime.tzinfo | None) -> datetime.datetime:
    """
    Attach a time zone to a naive datetime without changing its wall time

    Parameters
    ----------
    dt (datetime.datetime): The naive datetime
    tz (datetime.tzinfo | None): The time zone. None means the system time zone

    Returns
    ----------
    (datetime.datetime): The aware datetime
    """

    return dt.replace(tzinfo=tz) if tz else dt.astimezone()


@dataclass
class GitVersion:
    """The branch and commit the code is checked out at"""

    branch: str
    commit: str
    subject: str
    committed: datetime.datetime
    dirty: bool


def git_version() -> GitVersion | None:
    """
    Get the branch and latest commit of the git repository the bot runs from

    Returns
    ----------
    (GitVersion | None): The branch and commit. None if git or the repository isn't available
    """

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()

    try:
        branch = git("rev-parse", "--abbrev-ref", "HEAD")
        commit, timestamp, subject = git("log", "-1", "--format=%H%n%ct%n%s").split("\n", 2)
        dirty = bool(git("status", "--porcelain", "--untracked-files=no"))
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None

    return GitVersion(
        branch=branch,
        commit=commit,
        subject=subject,
        committed=datetime.datetime.fromtimestamp(int(timestamp), datetime.UTC),
        dirty=dirty,
    )


# The exceptions discord.py's tasks.loop retries instead of stopping on
RETRIED_TASK_EXCEPTIONS = (
    OSError,
    discord.GatewayNotFound,
    discord.ConnectionClosed,
    aiohttp.ClientError,
    asyncio.TimeoutError,
)


def log_errors(func):
    """
    Decorator for background task loops that logs exceptions instead of letting them stop the loop.
    Network errors are re-raised so discord.py can retry the iteration like it normally does.
    Put it below the @tasks.loop decorator. The decorated method's class needs a `bot` attribute

    Parameters
    ----------
    func (callable): The loop's coroutine function
    """

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            await func(self, *args, **kwargs)
        except RETRIED_TASK_EXCEPTIONS:
            raise
        except Exception:
            self.bot.logger.exception(f"Unhandled error in background task {func.__qualname__}")

    return wrapper


class RateLimiter:
    """Spaces out calls so that at most a given number happen per second"""

    def __init__(self, per_second: float):
        """
        Parameters
        ----------
        per_second (float): The maximum number of calls per second
        """

        self.interval = 1 / per_second
        self.next_slot = 0.0

    async def wait(self):
        """
        Wait until the next free slot. Call this before every rate limited call
        """

        now = asyncio.get_running_loop().time()
        slot = max(now, self.next_slot)
        self.next_slot = slot + self.interval
        await asyncio.sleep(slot - now)


class Paginator:
    """Interface for managing content. Divides your content into pages of 10 items each"""

    def __init__(self, content: list):
        """
        Parameters
        ----------
        content (list): The content you want to paginate
        """

        self.content = content
        self.total_page_count = ceil(len(content) / 10)
        self.current_page = 1

    def get_page(self, page: int) -> list | None:
        """
        Returns the page of the paginator

        Parameters
        ----------
        page (int): The page you want to get

        Returns
        ----------
        (list | None): The page you requested
        """

        if page < 1 or page > self.total_page_count:
            return None

        start_index = (page - 1) * 10
        end_index = page * 10

        return self.content[start_index:end_index]

    def get_current_page(self) -> list:
        """
        Returns the current page of the paginator

        Returns
        ----------
        (list): The current page of the paginator
        """

        return self.get_page(self.current_page)

    def next_page(self) -> list | None:
        """
        Returns the next page of the paginator

        Returns
        ----------
        (list): The next page of the paginator
        """

        self.current_page += 1
        return self.get_page(self.current_page)

    def previous_page(self) -> list | None:
        """
        Returns the previous page of the paginator

        Returns
        ----------
        (list): The previous page of the paginator
        """

        self.current_page -= 1
        return self.get_page(self.current_page)

    def first_page(self) -> list | None:
        """
        Returns the first page of the paginator

        Returns
        ----------
        (list): The first page of the paginator
        """

        self.current_page = 1
        return self.get_page(self.current_page)

    def last_page(self) -> list | None:
        """
        Returns the last page of the paginator

        Returns
        ----------
        (list): The last page of the paginator
        """

        self.current_page = self.total_page_count
        return self.get_page(self.current_page)


def put_text_in_box(
    image: np.ndarray,
    text: str,
    top_left: tuple,
    bottom_right: tuple,
    font_path: str = "./src/assets/fonts/impact.ttf",
    font_size: int = 10,
    color: tuple = (0, 0, 0),
):
    """
    Puts text inside a bounding box on the cv2 image with automatic text wrapping, using PIL for text rendering.

    Parameters
    ----------
    image (np.ndarray): Source cv2 image.
    text (str): Text to be put on the image.
    top_left (tuple): (x, y) Top-left corner of the bounding box.
    bottom_right (tuple): (x, y) Bottom-right corner of the bounding box.
    font_path (str): Path to the font file. Defaults to Impact font.
    font_size (int): Initial font size. Defaults to 10.
    color (tuple): Text color in RGB. Defaults to (0, 0, 0).
    """

    # Convert the cv2 image to a PIL image
    image_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image_pil)

    # Get coordinates of the bounding box
    x1, y1 = top_left
    x2, y2 = bottom_right

    # Get the width and height of the bounding box
    # We multiply by 0.9 to give some padding
    w, h = (x2 - x1) * 0.9, (y2 - y1) * 0.9

    # Add newlines to the text. Here we have gone with 15 characters per line
    # This is arbitrary, but seems to work well
    text = textwrap.fill(text, width=15)

    # Increase the font size as long as the next size still fits in the bounding box
    # We also have to check the height, since the text might be too tall for the box
    font = ImageFont.truetype(font_path, font_size)
    while True:
        next_font = ImageFont.truetype(font_path, font_size + 1)

        left, top, right, bottom = draw.multiline_textbbox((0, 0), text, font=next_font, align="center")

        if right - left >= w or bottom - top >= h:
            break

        font = next_font
        font_size += 1

    # Actually draw the text
    center_of_box = ((x1 + x2) // 2, (y1 + y2) // 2)
    draw.multiline_text(center_of_box, text, font=font, fill=color, align="center", anchor="mm")

    # Convert back to cv2 image format and update the original image
    cv2_image = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)
    np.copyto(image, cv2_image)
