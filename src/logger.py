import logging
import logging.handlers
import os
import sys
from datetime import datetime


class BotLogger:
    """Logging config for the bot"""

    def __init__(self):
        """
        Log to the console and to a new file in logs/ for every run
        """

        logger = logging.getLogger("discord")
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "[{asctime}] [{levelname:<8}] {name} - [{filename}] - [{funcName}] - {message}",
            "%Y-%m-%d %H:%M:%S",
            style="{",
        )

        if not os.path.exists("logs"):
            os.makedirs("logs")

        file_handler = logging.FileHandler(
            filename=f"logs/{datetime.now().strftime('%Y-%m-%d %H-%M')}.log",
            encoding="utf-8",
            mode="w",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler(sys.stdout)  # level is INFO we use stdout instead of stderr
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        self.logger = logger
