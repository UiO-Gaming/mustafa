import asyncio
import datetime
import functools
import re
import subprocess
from dataclasses import dataclass
from math import ceil

import aiohttp
import cv2
import discord
import numpy as np
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

UNICODE_FONT = "./src/assets/fonts/NotoSansCJK-Bold.ttc"

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


# Swaps the separators of Python's number formatting for Norwegian ones. The non-breaking space keeps
# Discord from splitting a number across two lines
NORWEGIAN_SEPARATORS = str.maketrans({",": "\u00a0", ".": ","})


def format_number(number: float, decimals: int | None = None) -> str:
    """
    Format a number the Norwegian way, with spaces between the thousands and a decimal comma

    Parameters
    ----------
    number (float): The number to format
    decimals (int | None): How many decimals to round to. None shows the number as is

    Returns
    ----------
    (str): The formatted number, like 1 234 567,8
    """

    formatted = f"{number:,}" if decimals is None else f"{number:,.{decimals}f}"
    return formatted.translate(NORWEGIAN_SEPARATORS)


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


@functools.lru_cache(maxsize=256)
def load_font(font_path: str, font_size: int) -> ImageFont.FreeTypeFont:
    """
    Load a font, reusing fonts that have already been loaded

    Parameters
    ----------
    font_path (str): Path to the font file
    font_size (int): The font size

    Returns
    ----------
    (ImageFont.FreeTypeFont): The font
    """

    return ImageFont.truetype(font_path, font_size)


# Chinese, Japanese and Korean characters. Lines can break between any two of them
CJK_CHARACTER = re.compile(r"[\u2e80-\u9fff\uac00-\ud7af\uf900-\ufaff\uff00-\uffef]")


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: float, break_words: bool) -> str | None:
    """
    Break text into lines that are at most max_width pixels wide.
    Lines break at spaces, and between Chinese, Japanese and Korean characters

    Parameters
    ----------
    text (str): The text to wrap
    font (ImageFont.FreeTypeFont): The font the text will be drawn with
    max_width (float): The maximum width of a line in pixels
    break_words (bool): Whether to split words too wide for a line of their own between their letters

    Returns
    ----------
    (str | None): The text with newlines added. None if a word is too wide and break_words is False
    """

    lines = []
    for paragraph in text.split("\n"):
        # Pieces that can go on separate lines, with the separator to put before them on the same line
        pieces = []
        for i, word in enumerate(paragraph.split(" ")):
            separator = " " if i else ""
            for piece in re.split(f"({CJK_CHARACTER.pattern})", word):
                if piece or not pieces:
                    pieces.append((separator, piece))
                    separator = ""

        line = ""
        for separator, piece in pieces:
            candidate = f"{line}{separator}{piece}" if line else piece
            if font.getlength(candidate) <= max_width:
                line = candidate
                continue

            if line:
                lines.append(line)
            if font.getlength(piece) <= max_width:
                line = piece
                continue
            if not break_words:
                return None

            line = ""
            for char in piece:
                if line and font.getlength(line + char) > max_width:
                    lines.append(line)
                    line = ""
                line += char
        lines.append(line)

    return "\n".join(lines)


def put_text_in_box(
    image: np.ndarray,
    text: str,
    top_left: tuple,
    bottom_right: tuple,
    font_path: str = UNICODE_FONT,
    color: tuple = (0, 0, 0),
):
    """
    Puts text inside a bounding box on the cv2 image, wrapped and as large as it can be while still fitting

    Parameters
    ----------
    image (np.ndarray): Source cv2 image.
    text (str): Text to be put on the image.
    top_left (tuple): (x, y) Top-left corner of the bounding box.
    bottom_right (tuple): (x, y) Bottom-right corner of the bounding box.
    font_path (str): Path to the font file. Defaults to Noto Sans CJK, which covers most scripts users write in.
    color (tuple): Text color in RGB. Defaults to (0, 0, 0).
    """

    # Convert the cv2 image to a PIL image
    image_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image_pil)

    # Leave 5% padding on every side of the box
    x1, y1 = top_left
    x2, y2 = bottom_right
    w, h = (x2 - x1) * 0.9, (y2 - y1) * 0.9

    def layout(font_size: int, break_words: bool) -> tuple[ImageFont.FreeTypeFont, str, tuple] | None:
        font = load_font(font_path, font_size)
        wrapped = wrap_text(text, font, w, break_words)
        if wrapped is None:
            return None
        return font, wrapped, draw.multiline_textbbox((0, 0), wrapped, font=font, align="center")

    def largest_fitting_size(break_words: bool) -> int:
        # Larger fonts never fit better, so binary search for the largest size that fits.
        # The font size can't usefully be larger than the box is tall. 0 means nothing fits
        low, high = 0, max(1, int(h))
        while low < high:
            middle = (low + high + 1) // 2
            result = layout(middle, break_words)
            if result and result[2][2] - result[2][0] <= w and result[2][3] - result[2][1] <= h:
                low = middle
            else:
                high = middle - 1
        return low

    # Splitting words in the middle makes them hard to read, so only do it when keeping them whole
    # would make the text less than half as big, like for one very long word
    whole_words_size = largest_fitting_size(break_words=False)
    split_words_size = largest_fitting_size(break_words=True)
    if whole_words_size and whole_words_size * 2 >= split_words_size:
        font, wrapped, (left, top, right, bottom) = layout(whole_words_size, break_words=False)
    else:
        font, wrapped, (left, top, right, bottom) = layout(max(1, split_words_size), break_words=True)

    # Center the drawn text itself in the box. Fonts leave space above and below the letters,
    # so centering the line height would push short text like "a" off center
    position = ((x1 + x2 - (right - left)) / 2 - left, (y1 + y2 - (bottom - top)) / 2 - top)
    draw.multiline_text(position, wrapped, font=font, fill=color, align="center")

    # Convert back to cv2 image format and update the original image
    cv2_image = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)
    np.copyto(image, cv2_image)
