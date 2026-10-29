from typing import Any
from typing import Iterable

from psycopg_pool import AsyncConnectionPool


class Database:
    """Runs queries on connections borrowed from a connection pool"""

    def __init__(self, pool: AsyncConnectionPool):
        """
        Parameters
        ----------
        pool (AsyncConnectionPool): The pool to borrow connections from
        """

        self.pool = pool

    async def execute(self, query: str, params: Iterable[Any] | None = None) -> int:
        """
        Runs a single statement

        Parameters
        ----------
        query (str): The SQL statement
        params (Iterable[Any] | None): Values for the statement's placeholders

        Returns
        ----------
        (int): The number of rows affected
        """

        async with self.pool.connection() as conn:
            cursor = await conn.execute(query, params)
            return cursor.rowcount

    async def execute_in_transaction(self, statements: list[tuple[str, Iterable[Any]]]):
        """
        Runs several statements in one transaction, so either all or none of them take effect

        Parameters
        ----------
        statements (list[tuple[str, Iterable[Any]]]): The SQL statements and their placeholder values
        """

        async with self.pool.connection() as conn, conn.transaction():
            for query, params in statements:
                await conn.execute(query, params)

    async def executemany(self, query: str, params_seq: Iterable[Iterable[Any]]):
        """
        Runs a statement once for each set of values

        Parameters
        ----------
        query (str): The SQL statement
        params_seq (Iterable[Iterable[Any]]): The values for each run
        """

        async with self.pool.connection() as conn, conn.cursor() as cursor:
            await cursor.executemany(query, params_seq)

    async def fetchone(self, query: str, params: Iterable[Any] | None = None) -> tuple | None:
        """
        Runs a query and returns its first row

        Parameters
        ----------
        query (str): The SQL query
        params (Iterable[Any] | None): Values for the query's placeholders

        Returns
        ----------
        (tuple | None): The first row. None if there are no rows
        """

        async with self.pool.connection() as conn:
            cursor = await conn.execute(query, params)
            return await cursor.fetchone()

    async def fetchall(self, query: str, params: Iterable[Any] | None = None) -> list[tuple]:
        """
        Runs a query and returns all its rows

        Parameters
        ----------
        query (str): The SQL query
        params (Iterable[Any] | None): Values for the query's placeholders

        Returns
        ----------
        (list[tuple]): The rows
        """

        async with self.pool.connection() as conn:
            cursor = await conn.execute(query, params)
            return await cursor.fetchall()
