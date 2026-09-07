import mysql.connector


class DatabaseManager:
    def __init__(self, host, user, password, database=None):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.conn = None

        self.connect()

    def connect(self):
        if self.database:
            self.conn = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
        else:
            self.conn = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password
            )

    def reconnect(self, database):
        if self.conn:
            self.conn.close()

        self.database = database
        self.connect()

    def show_databases(self):
        cursor = self.conn.cursor()
        cursor.execute("SHOW DATABASES")

        databases = []

        for row in cursor:
            databases.append(row[0])

        return databases

    def create_database(self, db_name):
        if db_name not in self.show_databases():
            cursor = self.conn.cursor()
            cursor.execute("CREATE DATABASE " + db_name)
            self.conn.commit()

            print("Database " + db_name + " created successfully.")

    def show_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("SHOW TABLES")

        tables = []

        for row in cursor:
            tables.append(row[0])

        return tables

    def create_table(self, table_name, params):
        if table_name not in self.show_tables():
            cursor = self.conn.cursor()

            query = "CREATE TABLE " + table_name + " " + params

            cursor.execute(query)
            self.conn.commit()

            print("Table " + table_name + " created successfully.")

    def column_exists(self, table_name, column_name):
        cursor = self.conn.cursor()

        query = "SHOW COLUMNS FROM " + table_name + " LIKE %s"

        cursor.execute(
            query,
            (column_name,)
        )

        return cursor.fetchone() is not None

    def add_column_if_missing(
        self,
        table_name,
        column_name,
        column_type
    ):
        if not self.column_exists(
            table_name,
            column_name
        ):
            cursor = self.conn.cursor()

            query = (
                "ALTER TABLE "
                + table_name
                + " ADD "
                + column_name
                + " "
                + column_type
            )

            cursor.execute(query)
            self.conn.commit()

            print(
                "Column "
                + column_name
                + " added to "
                + table_name
            )

    def insert_row(
        self,
        table_name,
        column_names,
        column_types,
        values
    ):
        cursor = self.conn.cursor()

        query = (
            "INSERT INTO "
            + table_name
            + " "
            + column_names
            + " VALUES "
            + column_types
        )

        cursor.execute(
            query,
            values
        )

        self.conn.commit()

    def get_all_rows(self, table_name):
        cursor = self.conn.cursor()

        query = "SELECT * FROM " + table_name

        cursor.execute(query)

        return cursor.fetchall()

    def get_rows_with_value(
        self,
        table_name,
        column_name,
        value
    ):
        cursor = self.conn.cursor()

        query = (
            "SELECT * FROM "
            + table_name
            + " WHERE "
            + column_name
            + " = %s"
        )

        cursor.execute(
            query,
            (value,)
        )

        return cursor.fetchall()

    def update_row(
        self,
        table_name,
        key_column,
        key_value,
        columns,
        values
    ):
        cursor = self.conn.cursor()

        parts = []

        for column in columns:
            parts.append(
                column + " = %s"
            )

        set_part = ", ".join(
            parts
        )

        query = (
            "UPDATE "
            + table_name
            + " SET "
            + set_part
            + " WHERE "
            + key_column
            + " = %s"
        )

        final_values = list(values)
        final_values.append(
            key_value
        )

        cursor.execute(
            query,
            final_values
        )

        self.conn.commit()

    def execute(
        self,
        query,
        values=None
    ):
        cursor = self.conn.cursor()

        if values:
            cursor.execute(
                query,
                values
            )
        else:
            cursor.execute(
                query
            )

        self.conn.commit()

        return cursor

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
        if self.conn:
            self.conn.close()