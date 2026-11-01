import discord


def error_warning(text: str) -> discord.Embed:
    """
    Creates an embed with a specified error message based on a warning template

    Parameters
    ----------
    text (str): The error message

    Returns
    ----------
    (discord.Embed): An embed object based on the template with the specified text
    """

    embed = discord.Embed(color=discord.Color.gold(), description=f"⚠️ {text}")
    return embed


def error_fatal(text: str) -> discord.Embed:
    """
    Creates an embed with a specified error message based on a warning template

    Parameters
    ----------
    text (str): The error message

    Returns
    ----------
    (discord.Embed): An embed object based on the template with the specified text
    """

    embed = discord.Embed(color=discord.Color.red(), description=f"❌ {text}")
    return embed


def success(text: str) -> discord.Embed:
    """
    Creates an embed with a specified message using a template signifying success.

    Parameters
    ----------
    text (str): The message

    Returns
    ----------
    (discord.Embed): An embed object based on the template with the specified text
    """

    embed = discord.Embed(color=discord.Color.green(), description=f"✅ {text}")
    return embed
