from abc import ABC, abstractmethod
import pandas as pd


class BaseConnector(ABC):
    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def run_query(self, sql: str) -> pd.DataFrame: ...

    # --- Dialect helpers (Postgres defaults; override in other connectors) ---

    def resolve_table(self, table: str) -> str:
        """Returns the table reference for use in SQL. Postgres needs no qualification."""
        return table

    def cast_float(self, expr: str) -> str:
        return f"CAST({expr} AS FLOAT)"

    def cast_string(self, expr: str) -> str:
        return f"{expr}::TEXT"

    def regex_match(self, expr: str, pattern: str) -> str:
        """Returns a SQL boolean expression: true when expr matches pattern. Postgres default."""
        return f"{expr} ~ '{pattern}'"

    def schema_query(self, table: str) -> str:
        return (
            f"SELECT column_name, data_type "
            f"FROM information_schema.columns "
            f"WHERE table_name = '{table}' "
            f"ORDER BY ordinal_position"
        )
