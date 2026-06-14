import os
import unicodedata

import psycopg2
from dotenv import load_dotenv

load_dotenv()


# Sehir isimlerini buyuk/kucuk harf, Turkce karakter ve sapka (â/î/û) farklarina
# dayanikli tek bir normalize anahtara cevirir. Boylece "Hakkâri" ile "Hakkari",
# "İzmir" ile "izmir" gibi yazimlar ayni anahtara dusup eslesir.
_TR_FOLD = {
    "ç": "c", "ğ": "g", "ı": "i", "İ": "i", "i": "i",
    "ö": "o", "ş": "s", "ü": "u", "â": "a", "î": "i", "û": "u",
}


def normalize_city(name):
    if name is None:
        return ""
    s = str(name).strip().lower()
    s = "".join(_TR_FOLD.get(ch, ch) for ch in s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "deprem_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)
