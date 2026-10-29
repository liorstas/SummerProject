import re
import threading

import mysql.connector


class DatabaseManager:
    ALLOWED_TABLES = {
        "users",
        "media_menu",
        "decrypted_media"
    }

    ALLOWED_COLUMNS = {
        "username_hash",
        "username",
        "password_hash",
        "client_ip",
        "client_port",
        "last_seen",
        "ddos_status",
        "is_online",
        "total_sent_media",
        "total_decoded_media",
        "id",
        "user_id",
        "media_type_id",
        "path_to_decrypted_media",
        "id_media",
        "image_path",
        "audio_path",
        "video_path"
    }

    def __init__(self, host, user, password, database=None):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.conn = None
        self.lock = threading.RLock()

        self.connect()

    def safe_table(self, name):
        if name not in self.ALLOWED_TABLES:
            raise ValueError("Table is not allowed")

        return "`" + name + "`"

    def safe_column(self, name):
        if name not in self.ALLOWED_COLUMNS:
            raise ValueError("Column is not allowed")

        return "`" + name + "`"

    def safe_database(self, name):
        if not isinstance(name, str):
            raise ValueError("Invalid database name")

        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError("Invalid database name")

        return "`" + name + "`"

    def connect(self):
        with self.lock:
            settings = {
                "host": self.host,
                "user": self.user,
                "password": self.password
            }

            if self.database:
                settings["database"] = self.database

            self.conn = mysql.connector.connect(**settings)

    def reconnect(self, database):
        with self.lock:
            if self.conn:
                self.conn.close()

            self.database = database
            self.connect()

    def show_databases(self):
        with self.lock:
            cursor = self.conn.cursor()

            try:
                cursor.execute("SHOW DATABASES")
                return [row[0] for row in cursor.fetchall()]
            finally:
                cursor.close()

    def create_database(self, db_name):
        safe_name = self.safe_database(db_name)

        with self.lock:
            if db_name in self.show_databases():
                return

            cursor = self.conn.cursor()

            try:
                cursor.execute(
                    "CREATE DATABASE " + safe_name
                )
                self.conn.commit()
            finally:
                cursor.close()

    def show_tables(self):
        with self.lock:
            cursor = self.conn.cursor()

            try:
                cursor.execute("SHOW TABLES")
                return [row[0] for row in cursor.fetchall()]
            finally:
                cursor.close()

    def create_table(self, table_name, params):
        safe_name = self.safe_table(table_name)

        if not isinstance(params, str):
            raise ValueError("Invalid table definition")

        with self.lock:
            if table_name in self.show_tables():
                return

            cursor = self.conn.cursor()

            try:
                cursor.execute(
                    "CREATE TABLE " + safe_name + " " + params
                )
                self.conn.commit()
            finally:
                cursor.close()

    def column_exists(self, table_name, column_name):
        safe_table = self.safe_table(table_name)
        self.safe_column(column_name)

        with self.lock:
            cursor = self.conn.cursor()

            try:
                cursor.execute(
                    "SHOW COLUMNS FROM "
                    + safe_table
                    + " LIKE %s",
                    (column_name,)
                )

                return cursor.fetchone() is not None
            finally:
                cursor.close()

    def add_column_if_missing(
        self,
        table_name,
        column_name,
        column_type
    ):
        safe_table = self.safe_table(table_name)
        safe_column = self.safe_column(column_name)

        if not isinstance(column_type, str):
            raise ValueError("Invalid column type")

        if not re.fullmatch(r"[A-Za-z0-9_(), ]+", column_type):
            raise ValueError("Invalid column type")

        with self.lock:
            if self.column_exists(table_name, column_name):
                return

            cursor = self.conn.cursor()

            try:
                cursor.execute(
                    "ALTER TABLE "
                    + safe_table
                    + " ADD "
                    + safe_column
                    + " "
                    + column_type
                )
                self.conn.commit()
            finally:
                cursor.close()

    def insert_row(
        self,
        table_name,
        column_names,
        column_types,
        values
    ):
        safe_table = self.safe_table(table_name)

        names = column_names.strip().strip("()")
        names = [name.strip() for name in names.split(",")]

        safe_names = ", ".join(
            self.safe_column(name) for name in names
        )

        if len(names) != len(values):
            raise ValueError("Column and value counts do not match")

        placeholders = "(" + ", ".join(
            ["%s"] * len(names)
        ) + ")"

        query = (
            "INSERT INTO "
            + safe_table
            + " ("
            + safe_names
            + ") VALUES "
            + placeholders
        )

        with self.lock:
            cursor = self.conn.cursor()

            try:
                cursor.execute(query, tuple(values))
                self.conn.commit()
            finally:
                cursor.close()

    def get_all_rows(self, table_name):
        safe_table = self.safe_table(table_name)

        with self.lock:
            cursor = self.conn.cursor()

            try:
                cursor.execute(
                    "SELECT * FROM " + safe_table
                )
                return cursor.fetchall()
            finally:
                cursor.close()

    def get_rows_with_value(
        self,
        table_name,
        column_name,
        value
    ):
        safe_table = self.safe_table(table_name)
        safe_column = self.safe_column(column_name)

        with self.lock:
            cursor = self.conn.cursor()

            try:
                cursor.execute(
                    "SELECT * FROM "
                    + safe_table
                    + " WHERE "
                    + safe_column
                    + " = %s",
                    (value,)
                )

                return cursor.fetchall()
            finally:
                cursor.close()

    def update_row(
        self,
        table_name,
        key_column,
        key_value,
        columns,
        values
    ):
        safe_table = self.safe_table(table_name)
        safe_key = self.safe_column(key_column)

        if len(columns) != len(values):
            raise ValueError("Column and value counts do not match")

        assignments = []

        for column in columns:
            assignments.append(
                self.safe_column(column) + " = %s"
            )

        query = (
            "UPDATE "
            + safe_table
            + " SET "
            + ", ".join(assignments)
            + " WHERE "
            + safe_key
            + " = %s"
        )

        parameters = list(values) + [key_value]

        with self.lock:
            cursor = self.conn.cursor()

            try:
                cursor.execute(query, tuple(parameters))
                self.conn.commit()
            finally:
                cursor.close()

    def execute(self, query, values=None):
        with self.lock:
            cursor = self.conn.cursor()

            try:
                if values is None:
                    cursor.execute(query)
                else:
                    cursor.execute(query, tuple(values))

                self.conn.commit()
            finally:
                cursor.close()

    def insert_decrypted_media(
        self,
        user_id,
        media_type_id,
        path
    ):
        self.insert_row(
            "decrypted_media",
            "(user_id, media_type_id, path_to_decrypted_media)",
            "(%s, %s, %s)",
            (
                user_id,
                media_type_id,
                path
            )
        )

    def close(self):
        with self.lock:
            if self.conn:
                self.conn.close()
                self.conn = None