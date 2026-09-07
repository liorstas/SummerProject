import os

IP = "127.0.0.1"
PORT = 9921
CHUNK_SIZE = 4096

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "lior_stas123",
    "database": "masker_db"
}