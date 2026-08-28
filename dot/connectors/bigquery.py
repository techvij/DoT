import pandas as pd

from dot.connectors.base import BaseConnector


class BigQueryConnector(BaseConnector):
    def connect(self) -> None:
        raise NotImplementedError("BigQuery connector not yet implemented")

    def run_query(self, sql: str) -> pd.DataFrame:
        raise NotImplementedError("BigQuery connector not yet implemented")
