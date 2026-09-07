import os
import socket

from constants import IP, PORT, BASE_DIR
from encrypt import Encryption


class Client:
    def __init__(self):
        self.sock = None
        self.encryptor = Encryption()

    def connect(self):
        self.sock = socket.socket()
        self.sock.connect((IP, PORT))

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def get_file_path(self, path):
        path = path.strip().strip('"')

        if os.path.isabs(path):
            return path

        normal_path = os.path.join(
            BASE_DIR,
            path
        )

        if os.path.exists(normal_path):
            return normal_path

        output_path = os.path.join(
            BASE_DIR,
            "output",
            path
        )

        if os.path.exists(output_path):
            return output_path

        return normal_path

    def register(self):
        self.connect()

        self.encryptor.send_encrypted_message(
            self.sock,
            "REGISTER"
        )

        username = input("Username: ")
        password = input("Password: ")

        self.encryptor.send_encrypted_message(
            self.sock,
            username
        )

        self.encryptor.send_encrypted_message(
            self.sock,
            password
        )

        result = self.encryptor.receive_encrypted_message(
            self.sock
        )

        print(result)

        self.close()

    def login(self):
        self.connect()

        self.encryptor.send_encrypted_message(
            self.sock,
            "LOGIN"
        )

        username = input("Username: ")
        password = input("Password: ")

        self.encryptor.send_encrypted_message(
            self.sock,
            username
        )

        self.encryptor.send_encrypted_message(
            self.sock,
            password
        )

        result = self.encryptor.receive_encrypted_message(
            self.sock
        )

        print(result)

        if result != "LOGIN_OK":
            self.close()
            return

        self.main_menu()

    def send_file(self, path):
        with open(path, "rb") as file:
            data = file.read()

        self.encryptor.send_encrypted_bytes(
            self.sock,
            data
        )

    def hide_data(self):
        menu = self.encryptor.receive_encrypted_message(
            self.sock
        )

        if menu == "NO_MEDIA":
            print("No media available")
            return

        print(menu)

        media_id = input(
            "Choose media id: "
        )

        self.encryptor.send_encrypted_message(
            self.sock,
            media_id
        )

        answer = self.encryptor.receive_encrypted_message(
            self.sock
        )

        if answer != "MEDIA_OK":
            print("Invalid media")
            return

        file_path = input(
            "File to hide: "
        )

        file_path = self.get_file_path(
            file_path
        )

        if not os.path.exists(file_path):
            print(
                "File does not exist:",
                file_path
            )

            self.encryptor.send_encrypted_bytes(
                self.sock,
                b""
            )

            answer = self.encryptor.receive_encrypted_message(
                self.sock
            )

            print(answer)
            return

        self.send_file(
            file_path
        )

        answer = self.encryptor.receive_encrypted_message(
            self.sock
        )

        print(answer)

    def decode_data(self):
        file_path = input(
            "File to decode: "
        )

        file_path = self.get_file_path(
            file_path
        )

        if not os.path.exists(file_path):
            print(
                "File does not exist:",
                file_path
            )

            self.encryptor.send_encrypted_bytes(
                self.sock,
                b""
            )

            amount_text = self.encryptor.receive_encrypted_message(
                self.sock
            )

            if amount_text == "":
                amount = 0
            else:
                amount = int(amount_text)

            print(
                "Found:",
                amount
            )

            return

        self.send_file(
            file_path
        )

        amount_text = self.encryptor.receive_encrypted_message(
            self.sock
        )

        if amount_text == "":
            amount = 0
        else:
            amount = int(amount_text)

        print(
            "Found:",
            amount
        )

        output_dir = os.path.join(
            BASE_DIR,
            "client_decoded"
        )

        os.makedirs(
            output_dir,
            exist_ok=True
        )

        for i in range(amount):
            server_path = self.encryptor.receive_encrypted_message(
                self.sock
            )

            image_data = self.encryptor.receive_encrypted_bytes(
                self.sock
            )

            file_name = os.path.basename(
                server_path
            )

            save_path = os.path.join(
                output_dir,
                file_name
            )

            with open(
                save_path,
                "wb"
            ) as file:
                file.write(image_data)

            print(
                "Saved:",
                save_path
            )

    def main_menu(self):
        while True:
            print()
            print("1. Hide data")
            print("2. Decode data")
            print("3. Logout")

            choice = input(
                "Choose: "
            )

            self.encryptor.send_encrypted_message(
                self.sock,
                choice
            )

            if choice == "1":
                self.hide_data()

            elif choice == "2":
                self.decode_data()

            elif choice == "3":
                self.close()
                break

            else:
                print("Invalid choice")

    def run(self):
        while True:
            print()
            print("1. Register")
            print("2. Login")
            print("3. Exit")

            choice = input(
                "Choose: "
            )

            if choice == "1":
                self.register()

            elif choice == "2":
                self.login()

            elif choice == "3":
                break

            else:
                print("Invalid choice")


if __name__ == "__main__":
    Client().run()