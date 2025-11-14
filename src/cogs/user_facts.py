import discord
import graphviz
import numpy as np
from discord import app_commands
from discord.ext import commands

from cogs.utils import discord_utils
from cogs.utils import embed_templates
from cogs.utils import misc_utils


class UserFacts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cursor = self.bot.db_connection.cursor()
        self.init_db()

        self.mbti_codes = {
            "INTJ",
            "INTP",
            "ENTJ",
            "ENTP",
            "INFJ",
            "INFP",
            "ENFJ",
            "ENFP",
            "ISTJ",
            "ISFJ",
            "ESTJ",
            "ESFJ",
            "ISTP",
            "ISFP",
            "ESTP",
            "ESFP",
        }
        self.mbti_list = list(self.mbti_codes)
        self.similarity_matrix = self.create_similarity_matrix()

    def init_db(self):
        """
        Create the necessary tables for the birthday cog to work
        """

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_facts (
                discord_id BIGINT PRIMARY KEY,
                mbti CHAR(4),
                height INT
            );
            """
        )

    height_group = app_commands.Group(name="høyde", description="Se, endre eller fjern høyde for brukere på serveren")

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @height_group.command(name="se", description="Se høyden til en bruker")
    async def height_see(self, interaction: discord.Interaction, bruker: discord.Member = None):
        """
        See the height of a user

        Parameters
        ----------
        interaction (discord.Interaction): The interaction object
        bruker (discord.Member): The user to see the height of
        """

        if not bruker:
            bruker = interaction.user

        self.cursor.execute(
            """
            SELECT height FROM user_facts
            WHERE discord_id = %s and height IS NOT NULL;
            """,
            (bruker.id,),
        )
        height = self.cursor.fetchone()

        if not height:
            return await interaction.response.send_message(
                embed=embed_templates.error_warning("Brukeren har ikke lagt inn høyden sin")
            )

        height = height[0]

        inches = height * (1 / 2.54)
        feet = int(inches * (1 / 12))
        inches = int(inches - (feet * 12))

        embed = discord.Embed(color=bruker.color)
        embed.add_field(name="Høyde", value=f"{height} cm")
        embed.add_field(name="Høyde (🦅🦅🇺🇸🦅🦅)", value=f"{feet}'{inches}\"")
        embed.set_author(name=bruker.global_name, icon_url=bruker.avatar)

        await interaction.response.send_message(embed=embed)

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @height_group.command(name="sett", description="Sett høyden din")
    @app_commands.rename(height_cm="høyde_cm")
    async def height_set(self, interaction: discord.Interaction, height_cm: app_commands.Range[int, 50, 250]):
        """
        Set your height

        Parameters
        ----------
        interaction (discord.Interaction): The interaction object
        height_cm (int): The height of the user
        """

        self.cursor.execute(
            """
            INSERT INTO user_facts (discord_id, height)
            VALUES (%s, %s)
            ON CONFLICT (discord_id) DO UPDATE
                SET height = %s;
            """,
            (interaction.user.id, height_cm, height_cm),
        )

        await interaction.response.send_message(embed=embed_templates.success("Høyde satt!"))

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @height_group.command(name="fjern", description="Fjern høyden din")
    async def height_remove(self, interaction: discord.Interaction):
        """
        Remove your height

        Parameters
        ----------
        interaction (discord.Interaction): The interaction object
        """

        self.cursor.execute(
            """
            UPDATE user_facts
            SET height = NULL
            WHERE discord_id = %s;
            """,
            (interaction.user.id,),
        )

        if self.cursor.rowcount == 0:
            return await interaction.response.send_message(
                embed=embed_templates.success("Du hadde ikke lagt inn høyden din fra før av men ok :)")
            )

        await interaction.response.send_message(embed=embed_templates.success("Høyde fjernet!"))

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @height_group.command(name="leaderboard", description="Se en leaderboard over høyder")
    async def height_leaderboard(self, interaction: discord.Interaction):
        """
        See a leaderboard of heights

        Parameters
        ----------
        interaction (discord.Interaction): The interaction object
        """

        self.cursor.execute(
            """
            SELECT discord_id, height FROM user_facts
            WHERE height IS NOT NULL
            ORDER BY height DESC;
            """
        )

        if not (result := self.cursor.fetchall()):
            return await interaction.response.send_message(
                embed=embed_templates.error_warning("Ingen har lagt inn høyden sin enda")
            )

        results_formatted = [f"**#{i+1}** <@{row[0]}> - `{row[1]}` cm" for i, row in enumerate(result)]

        paginator = misc_utils.Paginator(results_formatted)
        view = discord_utils.Scroller(paginator, interaction.user)

        embed = view.construct_embed(discord.Embed(title="Våre høyeste og laveste (👑)"))
        await interaction.response.send_message(embed=embed, view=view)

    mbti_group = app_commands.Group(name="mbti", description="Se, endre eller fjern MBTI for brukere på serveren")

    @app_commands.checks.bot_has_permissions(embed_links=True, attach_files=True)
    @app_commands.checks.cooldown(1, 2)
    @mbti_group.command(name="se", description="Se MBTI-en til en bruker")
    async def mbti_see(self, interaction: discord.Interaction, bruker: discord.Member = None):
        """
        See the MBTI of a user

        Parameters
        ----------
        interaction (discord.Interaction): The interaction object
        bruker (discord.Member): The user to see the MBTI of
        """

        if not bruker:
            bruker = interaction.user

        self.cursor.execute(
            """
            SELECT mbti FROM user_facts
            WHERE discord_id = %s AND mbti IS NOT NULL;
            """,
            (bruker.id,),
        )
        user_mbti = self.cursor.fetchone()

        if not user_mbti:
            return await interaction.response.send_message(
                embed=embed_templates.error_warning("Brukeren har ikke lagt inn MBTI-en sin")
            )

        user_mbti = user_mbti[0]

        embed = discord.Embed(color=bruker.color, title="MBTI", description=user_mbti)
        embed.set_author(name=bruker.global_name, icon_url=bruker.avatar)

        self.cursor.execute(
            """
            SELECT discord_id, mbti FROM user_facts
            WHERE mbti IS NOT NULL and discord_id != %s;
            """,
            (bruker.id,),
        )

        if not (results := self.cursor.fetchall()):
            return await interaction.response.send_message(embed=embed)

        others = []
        for discord_id, mbti in results:
            if user := self.bot.get_user(discord_id):
                others.append((user, mbti))
            elif user := await interaction.guild.fetch_member(discord_id):
                others.append((user, mbti))
            else:
                others.append((discord_id, mbti))

        self.create_mbti_graph((bruker, user_mbti), others)

        with open(f"src/assets/temp/{bruker.id}_mbti.png", "rb") as f:
            image = discord.File(f, filename=f"{bruker.id}_mbti.png")

        embed.set_image(url=f"attachment://{bruker.id}_mbti.png")
        await interaction.response.send_message(embed=embed, file=image)

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @mbti_group.command(name="sett", description="Sett MBTI-en din")
    async def mbti_set(self, interaction: discord.Interaction, mbti: str):
        """
        Set your MBTI

        Parameters
        ----------
        interaction (discord.Interaction): The interaction object
        mbti (str): The MBTI of the user
        """

        if mbti.upper() not in self.mbti_codes:
            return await interaction.response.send_message(embed=embed_templates.error_warning("Ugyldig MBTI"))

        self.cursor.execute(
            """
            INSERT INTO user_facts (discord_id, mbti)
            VALUES (%s, %s)
            ON CONFLICT (discord_id) DO UPDATE
                SET mbti = %s;
            """,
            (interaction.user.id, mbti.upper(), mbti.upper()),
        )

        await interaction.response.send_message(embed=embed_templates.success("MBTI satt!"))

    @mbti_set.autocomplete("mbti")
    async def mbti_set_autocomplete_callback(self, interaction: discord.Interaction, current: str):
        """
        Autocomplete for the MBTI set command

        Parameters
        ----------
        interaction (discord.Interaction): The interaction object
        current (str): The current input
        """

        return [
            app_commands.Choice(name=mbti, value=mbti) for mbti in self.mbti_codes if mbti.startswith(current.upper())
        ]

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @mbti_group.command(name="fjern", description="Fjern MBTI-en din")
    async def mbti_remove(self, interaction: discord.Interaction):
        """
        Remove your MBTI

        Parameters
        ----------
        interaction (discord.Interaction): The interaction object
        """

        self.cursor.execute(
            """
            UPDATE user_facts
            SET mbti = NULL
            WHERE discord_id = %s;
            """,
            (interaction.user.id,),
        )

        if self.cursor.rowcount == 0:
            return await interaction.response.send_message(
                embed=embed_templates.success("Du hadde ikke lagt inn MBTIen din fra før av men ok :)")
            )

        await interaction.response.send_message(embed=embed_templates.success("MBTI fjernet!"))

    @app_commands.checks.bot_has_permissions(embed_links=True)
    @app_commands.checks.cooldown(1, 2)
    @mbti_group.command(name="forklaring", description="Skjønner du ikke hva MBTI er? Her er en forklaring")
    async def mbti_explanation(self, interaction: discord.Interaction):
        """
        Get an explanation of MBTI

        Parameters
        ----------
        interaction (discord.Interaction): The interaction object
        """

        embed = discord.Embed(title="Hva er MBTI?", color=discord.Color.blurple())
        embed.description = (
            "MBTI er en forkortelse for Myers-Briggs Type Indicator. Det er en personlighetstest som"
            + " deler inn personligheter i 16 forskjellige typer. Hver type har fire bokstaver, og hver bokstav "
            + "representerer en egenskap. Egenskapene er:\n\n**I**ntrovert/**E**xtrovert\n**S**ensing/i**N**tuition\n"
            + "**T**hinking/**F**eeling\n**J**udging/**P**erceiving\n\nEr det vitenskapelig? Ikke akkurat. Er det gøy?"
            + " Definitvt.\n\nDu kan en personlighetstest [her](https://www.16personalities.com/free-personality-test)"
        )
        await interaction.response.send_message(embed=embed)

    def create_similarity_matrix(self):
        def similarity(mbti_1, mbti_2):
            similarity = 0
            for i in range(4):
                if mbti_1[i] == mbti_2[i]:
                    similarity += 1
            return similarity

        # Create an empty similarity matrix
        similarity_matrix = np.zeros((len(self.mbti_list), len(self.mbti_list)))

        # Fill the similarity matrix
        for i, mbti in enumerate(self.mbti_list):
            for j, mbti2 in enumerate(self.mbti_list):
                similarity_matrix[i, j] = similarity(mbti, mbti2)

        return similarity_matrix

    def create_mbti_graph(self, user_mbti: tuple[discord.Member, str], others: list[tuple[discord.Member, str]]):
        user, mbti = user_mbti

        # Create a Graphviz graph
        graph = graphviz.Graph(engine="neato", format="png")
        graph.attr("graph", overlap="false", splines="True")
        graph.node_attr["style"] = "filled"
        graph.node_attr["shape"] = "circle"

        # Invoking user's node
        graph.node(str(user.global_name), f"{user.global_name}\n{mbti}", color="green")

        user_index = self.mbti_list.index(mbti)

        # Add nodes and edges to other users
        for other_user, other_mbti in others:
            other_index = self.mbti_list.index(other_mbti)

            similarity = 1 / self.similarity_matrix[user_index, other_index]
            edge_length = 5 - similarity

            graph.node(other_user.global_name, f"{other_user.global_name}\n{other_mbti}")
            graph.edge(user.global_name, other_user.global_name, len=str(edge_length))

        graph.render(f"{user.id}_mbti", directory="./src/assets/temp", view=False, overwrite_source=True)


async def setup(bot: commands.Bot):
    """
    Add the cog to the bot on extension load

    Parameters
    ----------
    bot (commands.Bot): Bot instance
    """

    await bot.add_cog(UserFacts(bot))
