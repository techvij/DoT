import logging
import os

import pandas as pd
import psycopg2
from dotenv import load_dotenv

from dot.connectors.base import BaseConnector

logger = logging.getLogger("dot")


class PostgresConnector(BaseConnector):
    def __init__(self, env_file: str = ".env"):
        load_dotenv(env_file, override=False)
        self._conn = None
        self._dsn = (
            f"{os.getenv('POSTGRES_USER')}@{os.getenv('POSTGRES_HOST')}:"
            f"{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
        )

    def connect(self) -> None:
        logger.info(f"Connecting to Postgres: {self._dsn}")
        self._conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            dbname=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
        )
        logger.info("Postgres connection established")

    def run_query(self, sql: str) -> pd.DataFrame:
        if self._conn is None or self._conn.closed:
            self.connect()
        logger.debug(f"SQL:\n{sql.strip()}")
        return pd.read_sql_query(sql, self._conn)
