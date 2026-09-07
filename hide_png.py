import os
from datetime import datetime

from constants import BASE_DIR
from create_tables import get_full_path
from encrypt import Encryption


class DataHider:
    def __init__(self, client_socket, db_manager, user_id):
        self.client_socket = client_socket
        self.db_manager = db_manager
        self.user_id = user_id
        self.encryptor = Encryption()

    def get_media(self):
        rows = self.db_manager.get_all_rows("media_menu")

        images = []

        for row in rows:
            if row[1]:
                images.append(row)

        if not images:
            self.encryptor.send_encrypted_message(
                self.client_socket,
                "NO_MEDIA"
            )
            return None

        menu = ""

        for row in images:
            menu += str(row[0]) + ": " + row[1] + "\n"

        self.encryptor.send_encrypted_message(
            self.client_socket,
            menu
        )

        media_id = self.encryptor.receive_encrypted_message(
            self.client_socket
        )

        for row in images:
            if str(row[0]) == media_id:
                self.encryptor.send_encrypted_message(
                    self.client_socket,
                    "MEDIA_OK"
                )
                return row

        self.encryptor.send_encrypted_message(
            self.client_socket,
            "INVALID_MEDIA"
        )

        return None

    def create_hidden_file(self, media_path, hidden_data):
        output_dir = os.path.join(
            BASE_DIR,
            "output"
        )

        os.makedirs(
            output_dir,
            exist_ok=True
        )

        file_name = (
            "hidden_"
            + datetime.now().strftime("%Y%m%d_%H%M%S")
            + ".jpg"
        )

        output_path = os.path.join(
            output_dir,
            file_name
        )

        with open(media_path, "rb") as media_file:
            original_data = media_file.read()

        with open(output_path, "wb") as output_file:
            output_file.write(original_data)
            output_file.write(hidden_data)

        return os.path.join(
            "output",
            file_name
        )

    def run(self):
        selected_media = self.get_media()

        if not selected_media:
            return None

        hidden_data = self.encryptor.receive_encrypted_bytes(
            self.client_socket
        )

        if not hidden_data:
            self.encryptor.send_encrypted_message(
                self.client_socket,
                "No file received"
            )
            return None

        media_path = get_full_path(
            selected_media[1]
        )

        if not os.path.exists(media_path):
            self.encryptor.send_encrypted_message(
                self.client_socket,
                "Media file was not found"
            )
            return None

        output_path = self.create_hidden_file(
            media_path,
            hidden_data
        )

        self.encryptor.send_encrypted_message(
            self.client_socket,
            "OK:" + output_path
        )

        return output_path