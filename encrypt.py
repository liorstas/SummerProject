import os
from Crypto.Cipher import AES
from constants import BASE_DIR


class Encryption:
    def __init__(self):
        self.key_path = os.path.join(BASE_DIR, "masker.key")
        self.key = self.load_key()

    def load_key(self):
        if not os.path.exists(self.key_path):
            key = os.urandom(32)

            with open(self.key_path, "wb") as file:
                file.write(key)

            return key

        with open(self.key_path, "rb") as file:
            key = file.read()

        if len(key) != 32:
            raise ValueError("The encryption key is not valid")

        return key

    def encrypt_data(self, data):
        cipher = AES.new(
            self.key,
            AES.MODE_GCM
        )

        encrypted_data, tag = cipher.encrypt_and_digest(data)

        return cipher.nonce + tag + encrypted_data

    def decrypt_data(self, data):
        nonce = data[:16]
        tag = data[16:32]
        encrypted_data = data[32:]

        cipher = AES.new(
            self.key,
            AES.MODE_GCM,
            nonce=nonce
        )

        return cipher.decrypt_and_verify(
            encrypted_data,
            tag
        )

    def receive_exact(self, sock, size):
        data = b""

        while len(data) < size:
            part = sock.recv(
                size - len(data)
            )

            if not part:
                raise ConnectionError(
                    "Connection closed"
                )

            data += part

        return data

    def send_encrypted_bytes(self, sock, data):
        encrypted_data = self.encrypt_data(data)

        size = len(encrypted_data)

        sock.sendall(
            size.to_bytes(
                8,
                "big"
            )
        )

        sock.sendall(
            encrypted_data
        )

    def receive_encrypted_bytes(self, sock):
        size_data = self.receive_exact(
            sock,
            8
        )

        size = int.from_bytes(
            size_data,
            "big"
        )

        encrypted_data = self.receive_exact(
            sock,
            size
        )

        return self.decrypt_data(
            encrypted_data
        )

    def send_encrypted_message(self, sock, message):
        data = str(message).encode("utf-8")

        self.send_encrypted_bytes(
            sock,
            data
        )

    def receive_encrypted_message(self, sock):
        data = self.receive_encrypted_bytes(
            sock
        )

        return data.decode("utf-8")