import os
import time
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

from utils.singleton import Singleton

# Charge le .env..
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

IDLE_BEFORE_CHECK = 30  # secondes

class DBConnection(metaclass=Singleton):
    """Connexion unique à PostgreSQL, partagée par toutes les DAO."""

    def __init__(self):
        self.__connection = self._connect()
        self.__last_use = time.monotonic()

    @staticmethod
    def _connect():
        return psycopg2.connect(
            host=os.environ["POSTGRES_HOST"],
            port=os.environ["POSTGRES_PORT"],
            database=os.environ["POSTGRES_DATABASE"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            options=f"-c search_path={os.environ['POSTGRES_SCHEMA']}",
            cursor_factory=RealDictCursor,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=3,
        )

    def _is_alive(self) -> bool:
        if self.__connection.closed:
            return False
        if time.monotonic() - self.__last_use < IDLE_BEFORE_CHECK:
            return True
        try:
            with self.__connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            self.__connection.commit()
            return True
        except psycopg2.Error:
            return False

    @property
    def connection(self):
        """Renvoie la connexion, rouverte si le serveur l'a coupée."""
        if not self._is_alive():
            self.__connection = self._connect()
        self.__last_use = time.monotonic()
        return self.__connection
