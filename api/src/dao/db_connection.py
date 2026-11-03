import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

from utils.singleton import Singleton

# Charge le .env situé à la racine du dépôt
load_dotenv(Path(__file__).resolve().parents[3] / ".env")


class DBConnection(metaclass=Singleton):
    """Connexion unique à PostgreSQL, partagée par toutes les DAO."""

    def __init__(self):
        self.__connection = psycopg2.connect(
            host=os.environ["POSTGRES_HOST"],
            port=os.environ["POSTGRES_PORT"],
            database=os.environ["POSTGRES_DATABASE"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            options=f"-c search_path={os.environ['POSTGRES_SCHEMA']}",
            cursor_factory=RealDictCursor,
        )

    @property
    def connection(self):
        """Renvoie la connexion ouverte."""
        return self.__connection
