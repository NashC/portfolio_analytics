import sqlite3
import os
from typing import Optional

class Database:
    def __init__(self):
        db_path = os.path.join('data', 'historical_price_data', 'prices.db')
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def execute(self, query: str, params: Optional[tuple] = None) -> sqlite3.Cursor:
        if params:
            return self.cursor.execute(query, params)
        return self.cursor.execute(query)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close() 