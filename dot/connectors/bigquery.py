import logging

import pandas as pd

from dot.connectors.base import BaseConnector

logger = logging.getLogger("dot")

try:
    from google.cloud import bigquery
    from google.oauth2 import service_account
    _BQ_AVAILABLE = True
except ImportError:
    _BQ_AVAILABLE = False


class BigQueryConnector(BaseConnector):
    """
    BigQuery connector. Auth precedence:
      1. credentials_file (service account JSON) — set in connection config
      2. Application Default Credentials — gcloud auth application-default login,
         or automatic in Cloud Shell / GCE / Cloud Run
    """

    def __init__(self, config: dict):
        self.project = config["project"]
        self.dataset = config.get("dataset", "")
        self.credentials_file = config.get("credentials_file")
        self._client = None

    def connect(self) -> None:
        if not _BQ_AVAILABLE:
            raise ImportError(
                "google-cloud-bigquery is not installed. "
                "Run: pip install google-cloud-bigquery pyarrow"
            )
        logger.info(
            f"Connecting to BigQuery: project={self.project}, dataset={self.dataset or '(none)'}"
        )
        if self.credentials_file:
            logger.info(f"Using service account credentials: {self.credentials_file}")
            creds = service_account.Credentials.from_service_account_file(
                self.credentials_file,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            self._client = bigquery.Client(project=self.project, credentials=creds)
        else:
            logger.info("Using Application Default Credentials (ADC)")
            self._client = bigquery.Client(project=self.project)
        logger.info("BigQuery client ready")

    def run_query(self, sql: str) -> pd.DataFrame:
        if self._client is None:
            self.connect()
        logger.debug(f"SQL:\n{sql.strip()}")
        return self._client.query(sql).to_dataframe()

    # --- Table resolution ---

    def _parse_table(self, table: str) -> tuple[str, str, str]:
        """
        Splits a table string into (project, dataset, table_name).

          'orders'                       → config project + config dataset
          'my_dataset.orders'            → config project + given dataset
          'my-project.my_dataset.orders' → fully self-contained
        """
        parts = table.split(".")
        if len(parts) == 3:
            return parts[0], parts[1], parts[2]
        elif len(parts) == 2:
            return self.project, parts[0], parts[1]
        else:
            if not self.dataset:
                raise ValueError(
                    f"Table '{table}' has no dataset qualifier and no default 'dataset' "
                    f"is set in the connection config."
                )
            return self.project, self.dataset, parts[0]

    def resolve_table(self, table: str) -> str:
        """
        Returns a backtick-quoted fully qualified table reference for use in SQL.
        Backticks handle project IDs that contain hyphens (e.g. my-project-123).
        """
        project, dataset, table_name = self._parse_table(table)
        return f"`{project}.{dataset}.{table_name}`"

    # --- Dialect overrides ---

    def cast_float(self, expr: str) -> str:
        return f"CAST({expr} AS FLOAT64)"

    def cast_string(self, expr: str) -> str:
        return f"CAST({expr} AS STRING)"

    def schema_query(self, table: str) -> str:
        project, dataset, table_name = self._parse_table(table)
        return (
            f"SELECT column_name, data_type "
            f"FROM `{project}.{dataset}.INFORMATION_SCHEMA.COLUMNS` "
            f"WHERE table_name = '{table_name}' "
            f"ORDER BY ordinal_position"
        )
