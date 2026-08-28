import logging
import os

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
      1. credentials_file (service account JSON) — explicit, always wins
      2. Cloud Shell detected (GOOGLE_CLOUD_SHELL=true) — uses gcloud auth
         print-access-token directly, same as bq CLI. Needed because
         google.auth.default() falls back to the GCE metadata server in Cloud
         Shell which returns the VM identity, not the user's identity.
      3. Application Default Credentials — works correctly on GCE, Cloud Run,
         GKE, and local dev with `gcloud auth application-default login`.
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
                "Run: pip install google-cloud-bigquery pyarrow db-dtypes"
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

        elif os.environ.get("GOOGLE_CLOUD_SHELL") == "true":
            # google.auth.default() is unreliable in Cloud Shell — it falls back to the
            # GCE metadata server (VM identity, not the logged-in user). Use the gcloud
            # token directly, same credential chain as `bq` CLI and all gcloud commands.
            logger.info("Using gcloud token credentials (Cloud Shell detected via GOOGLE_CLOUD_SHELL)")
            import subprocess
            from google.oauth2 import credentials as oauth2_credentials
            _token = subprocess.check_output(
                ["gcloud", "auth", "print-access-token"]
            ).decode().strip()
            creds = oauth2_credentials.Credentials(_token)

        else:
            logger.info("Using Application Default Credentials (ADC)")
            import google.auth
            creds, _ = google.auth.default()

        self._client = bigquery.Client(project=self.project, credentials=creds)
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
