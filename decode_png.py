import os
from datetime import datetime

from constants import BASE_DIR
from encrypt import Encryption


class ImageExtractor:
    def __init__(self, client_socket, db_manager, user_id):
        self.client_socket = client_socket
        self.db_manager = db_manager
        self.user_id = user_id

        self.encryptor = Encryption()
        self.found_images = []

    def extract_images(self, media_data):
        if not media_data:
            return

        jpeg_start = b"\xff\xd8"
        jpeg_end = b"\xff\xd9"

        original_end = media_data.find(jpeg_end)

        if original_end == -1:
            return

        position = original_end + 2
        count = 1

        while True:
            start = media_data.find(
                jpeg_start,
                position
            )

            if start == -1:
                break

            end = media_data.find(
                jpeg_end,
                start
            )

            if end == -1:
                break

            end += 2

            image_data = media_data[start:end]

            output_folder = os.path.join(
                BASE_DIR,
                "decoded"
            )

            os.makedirs(
                output_folder,
                exist_ok=True
            )

            file_name = (
                "decoded_"
                + datetime.now().strftime("%Y%m%d_%H%M%S")
                + "_"
                + str(count)
                + ".jpg"
            )

            full_path = os.path.join(
                output_folder,
                file_name
            )

            with open(full_path, "wb") as file:
                file.write(image_data)

            relative_path = os.path.join(
                "decoded",
                file_name
            )

            self.found_images.append(
                (
                    relative_path,
                    image_data
                )
            )

            self.db_manager.insert_decrypted_media(
                self.user_id,
                1,
                relative_path
            )

            count += 1
            position = end

    def send_results(self):
        amount = len(self.found_images)

        self.encryptor.send_encrypted_message(
            self.client_socket,
            str(amount)
        )

        for path, image_data in self.found_images:
            self.encryptor.send_encrypted_message(
                self.client_socket,
                path
            )

            self.encryptor.send_encrypted_bytes(
                self.client_socket,
                image_data
            )

    def run(self):
        media_data = self.encryptor.receive_encrypted_bytes(
            self.client_socket
        )

        if not media_data:
            self.encryptor.send_encrypted_message(
                self.client_socket,
                "0"
            )

            return 0

        self.extract_images(
            media_data
        )

        self.send_results()

        return len(self.found_images)