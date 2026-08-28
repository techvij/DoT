from abc import ABC, abstractmethod
import pandas as pd


class BaseConnector(ABC):
    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def run_query(self, sql: str) -> pd.DataFrame: ...
