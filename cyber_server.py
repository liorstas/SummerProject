import csv
import hashlib
import os
import socket
import threading
from datetime import datetime

import tkinter as tk
from tkinter import scrolledtext

import pygame

from constants import IP, PORT, DB_CONFIG, BASE_DIR
from create_tables import create_all_tables, populate_media_menu, fix_old_paths
from db_manager import DatabaseManager
from decode_png import ImageExtractor
from encrypt import Encryption
from hide_png import DataHider


class Server:
    def __init__(self):
        self.db = DatabaseManager(
            DB_CONFIG["host"],
            DB_CONFIG["user"],
            DB_CONFIG["password"]
        )

        self.db.create_database(
            DB_CONFIG["database"]
        )

        self.db.reconnect(
            DB_CONFIG["database"]
        )

        create_all_tables(
            self.db
        )

        populate_media_menu(
            self.db
        )

        fix_old_paths(
            self.db
        )

        self.db.execute(
            "UPDATE clients SET is_online = 0"
        )

        self.encryptor = Encryption()

        self.root = tk.Tk()
        self.root.withdraw()

        self.log_text = None
        self.online_list = None
        self.all_list = None

    def get_hash(self, text):
        return hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()

    def register_user(self, sock):
        username = self.encryptor.receive_encrypted_message(
            sock
        )

        password = self.encryptor.receive_encrypted_message(
            sock
        )

        username = username.strip()

        if len(username) < 3:
            self.encryptor.send_encrypted_message(
                sock,
                "Username is too short"
            )

            return

        if len(password) < 4:
            self.encryptor.send_encrypted_message(
                sock,
                "Password is too short"
            )

            return

        username_hash = self.get_hash(
            username.lower()
        )

        password_hash = self.get_hash(
            password
        )

        users = self.db.get_rows_with_value(
            "users",
            "username_hash",
            username_hash
        )

        if users:
            self.encryptor.send_encrypted_message(
                sock,
                "User already exists"
            )

            return

        self.db.insert_row(
            "users",
            "(username_hash, username, password_hash)",
            "(%s, %s, %s)",
            (
                username_hash,
                username,
                password_hash
            )
        )

        self.encryptor.send_encrypted_message(
            sock,
            "REGISTER_OK"
        )

        self.write_log(
            "Registered: "
            + username
        )

    def login_user(self, sock):
        username = self.encryptor.receive_encrypted_message(
            sock
        ).strip()

        password = self.encryptor.receive_encrypted_message(
            sock
        )

        username_hash = self.get_hash(
            username.lower()
        )

        password_hash = self.get_hash(
            password
        )

        users = self.db.get_rows_with_value(
            "users",
            "username_hash",
            username_hash
        )

        if not users:
            self.encryptor.send_encrypted_message(
                sock,
                "User does not exist"
            )

            return None

        user = users[0]

        if user[2] != password_hash:
            self.encryptor.send_encrypted_message(
                sock,
                "Wrong password"
            )

            return None

        self.encryptor.send_encrypted_message(
            sock,
            "LOGIN_OK"
        )

        return (
            username_hash,
            user[1]
        )

    def connect_client(
        self,
        client_id,
        username,
        address
    ):
        rows = self.db.get_rows_with_value(
            "clients",
            "client_id",
            client_id
        )

        if rows:
            self.db.update_row(
                "clients",
                "client_id",
                client_id,
                [
                    "client_ip",
                    "client_port",
                    "last_seen",
                    "is_online"
                ],
                [
                    address[0],
                    address[1],
                    datetime.now(),
                    True
                ]
            )

        else:
            self.db.insert_row(
                "clients",
                "(client_id, username, client_ip, client_port, last_seen, ddos_status, is_online, total_sent_media, total_decoded_media)",
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    client_id,
                    username,
                    address[0],
                    address[1],
                    datetime.now(),
                    False,
                    True,
                    0,
                    0
                )
            )

    def add_stat(
        self,
        client_id,
        column
    ):
        rows = self.db.get_rows_with_value(
            "clients",
            "client_id",
            client_id
        )

        if not rows:
            return

        row = rows[0]

        if column == "total_sent_media":
            current = row[7]

        else:
            current = row[8]

        self.db.update_row(
            "clients",
            "client_id",
            client_id,
            [column],
            [current + 1]
        )

    def handle_client(
        self,
        sock,
        address
    ):
        client_id = None
        username = None

        try:
            action = self.encryptor.receive_encrypted_message(
                sock
            )

            if action == "REGISTER":
                self.register_user(
                    sock
                )

                return

            if action != "LOGIN":
                return

            login_result = self.login_user(
                sock
            )

            if not login_result:
                return

            client_id = login_result[0]
            username = login_result[1]

            self.connect_client(
                client_id,
                username,
                address
            )

            self.write_log(
                username
                + " connected"
            )

            self.refresh_lists()

            while True:
                choice = self.encryptor.receive_encrypted_message(
                    sock
                )

                if choice == "1":
                    hider = DataHider(
                        sock,
                        self.db,
                        client_id
                    )

                    result = hider.run()

                    if result:
                        self.add_stat(
                            client_id,
                            "total_sent_media"
                        )

                        self.refresh_lists()

                elif choice == "2":
                    extractor = ImageExtractor(
                        sock,
                        self.db,
                        client_id
                    )

                    found = extractor.run()

                    self.add_stat(
                        client_id,
                        "total_sent_media"
                    )

                    if found > 0:
                        self.add_stat(
                            client_id,
                            "total_decoded_media"
                        )

                    self.refresh_lists()

                elif choice == "3":
                    break

        except Exception as error:
            self.write_log(
                "Error: "
                + str(error)
            )

        finally:
            if client_id:
                self.db.update_row(
                    "clients",
                    "client_id",
                    client_id,
                    [
                        "is_online",
                        "last_seen"
                    ],
                    [
                        False,
                        datetime.now()
                    ]
                )

                self.refresh_lists()

            sock.close()

    def refresh_lists(self):
        if not self.online_list:
            return

        def refresh():
            self.online_list.delete(
                0,
                tk.END
            )

            self.all_list.delete(
                0,
                tk.END
            )

            clients = self.db.get_all_rows(
                "clients"
            )

            for client in clients:
                text = (
                    client[1]
                    + " | sent: "
                    + str(client[7])
                    + " | decoded: "
                    + str(client[8])
                )

                self.all_list.insert(
                    tk.END,
                    text
                )

                if client[6]:
                    self.online_list.insert(
                        tk.END,
                        text
                    )

        self.root.after(
            0,
            refresh
        )

    def write_log(self, text):
        if not self.log_text:
            return

        def update():
            self.log_text.config(
                state=tk.NORMAL
            )

            self.log_text.insert(
                tk.END,
                text + "\n"
            )

            self.log_text.config(
                state=tk.DISABLED
            )

        self.root.after(
            0,
            update
        )

    def play_audio(self):
        audio_path = os.path.join(
            BASE_DIR,
            "lior_intro.wav"
        )

        if not os.path.exists(audio_path):
            return

        try:
            pygame.mixer.init()

            pygame.mixer.music.load(
                audio_path
            )

            pygame.mixer.music.play()

        except Exception:
            pass

    def show_splash(self):
        splash = tk.Toplevel(
            self.root
        )

        splash.geometry(
            "500x250"
        )

        splash.configure(
            bg="#111111"
        )

        tk.Label(
            splash,
            text="MASKER",
            font=("Arial", 30, "bold"),
            fg="white",
            bg="#111111"
        ).pack(
            pady=(50, 10)
        )

        tk.Label(
            splash,
            text="LIOR STAS",
            font=("Arial", 17),
            fg="white",
            bg="#111111"
        ).pack()

        tk.Label(
            splash,
            text="Version 2.0",
            fg="white",
            bg="#111111"
        ).pack(
            pady=5
        )

        splash.after(
            2500,
            splash.destroy
        )

        self.root.wait_window(
            splash
        )

    def export_statistics(self):
        path = os.path.join(
            BASE_DIR,
            "server_statistics.csv"
        )

        clients = self.db.get_all_rows(
            "clients"
        )

        with open(
            path,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.writer(
                file
            )

            writer.writerow(
                [
                    "username",
                    "online",
                    "sent files",
                    "decoded files"
                ]
            )

            for client in clients:
                writer.writerow(
                    [
                        client[1],
                        client[6],
                        client[7],
                        client[8]
                    ]
                )

        self.write_log(
            "Statistics saved"
        )

    def start_server(self):
        server_socket = socket.socket()

        server_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        server_socket.bind(
            (
                IP,
                PORT
            )
        )

        server_socket.listen()

        self.write_log(
            "Server started"
        )

        while True:
            sock, address = server_socket.accept()

            thread = threading.Thread(
                target=self.handle_client,
                args=(
                    sock,
                    address
                ),
                daemon=True
            )

            thread.start()

    def create_gui(self):
        self.play_audio()
        self.show_splash()

        self.root.deiconify()

        self.root.title(
            "MASKER Server"
        )

        self.root.geometry(
            "700x600"
        )

        tk.Label(
            self.root,
            text="Server Log",
            font=("Arial", 14, "bold")
        ).pack(
            pady=5
        )

        self.log_text = scrolledtext.ScrolledText(
            self.root,
            height=10,
            state=tk.DISABLED
        )

        self.log_text.pack(
            fill="x",
            padx=15
        )

        tk.Label(
            self.root,
            text="Connected Now"
        ).pack(
            pady=(10, 2)
        )

        self.online_list = tk.Listbox(
            self.root,
            height=7
        )

        self.online_list.pack(
            fill="x",
            padx=15
        )

        tk.Label(
            self.root,
            text="All Clients"
        ).pack(
            pady=(10, 2)
        )

        self.all_list = tk.Listbox(
            self.root,
            height=8
        )

        self.all_list.pack(
            fill="x",
            padx=15
        )

        tk.Button(
            self.root,
            text="Export Statistics",
            command=self.export_statistics
        ).pack(
            pady=10
        )

        self.refresh_lists()

        thread = threading.Thread(
            target=self.start_server,
            daemon=True
        )

        thread.start()

        self.root.mainloop()


if __name__ == "__main__":
    Server().create_gui()