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

        create_all_tables(self.db)
        populate_media_menu(self.db)
        fix_old_paths(self.db)

        self.db.execute(
            "UPDATE clients SET is_online = 0"
        )

        self.encryptor = Encryption()

        self.root = tk.Tk()
        self.root.withdraw()

        self.log_text = None
        self.online_list = None
        self.all_list = None

        self.online_count_label = None
        self.registered_count_label = None
        self.sent_count_label = None
        self.decoded_count_label = None

    def get_hash(self, text):
        return hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()

    def register_user(self, sock):
        username = self.encryptor.receive_encrypted_message(
            sock
        ).strip()

        password = self.encryptor.receive_encrypted_message(
            sock
        )

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
            "Registered: " + username
        )

        self.refresh_lists()

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

    def connect_client(self, client_id, username, address):
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

    def add_stat(self, client_id, column):
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

    def handle_client(self, sock, address):
        client_id = None
        username = None

        try:
            action = self.encryptor.receive_encrypted_message(
                sock
            )

            if action == "REGISTER":
                self.register_user(sock)
                return

            if action != "LOGIN":
                return

            login_result = self.login_user(sock)

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
                username + " connected"
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

                else:
                    self.encryptor.send_encrypted_message(
                        sock,
                        "Invalid option"
                    )

        except ConnectionError:
            if username:
                self.write_log(
                    username + " disconnected"
                )

        except Exception as error:
            self.write_log(
                "Error: " + str(error)
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

            try:
                sock.close()
            except:
                pass

    def get_all_statistics(self):
        users = self.db.get_all_rows(
            "users"
        )

        data = []

        total_users = 0
        total_online = 0
        total_sent = 0
        total_decoded = 0

        for user in users:
            total_users += 1

            username_hash = user[0]
            username = user[1]

            clients = self.db.get_rows_with_value(
                "clients",
                "client_id",
                username_hash
            )

            if clients:
                client = clients[0]

                sent = client[7]
                decoded = client[8]
                online = client[6]
                last_seen = client[4]

                if online:
                    total_online += 1

            else:
                sent = 0
                decoded = 0
                online = False
                last_seen = None

            total_sent += sent
            total_decoded += decoded

            data.append(
                {
                    "username": username,
                    "sent": sent,
                    "decoded": decoded,
                    "online": online,
                    "last_seen": last_seen
                }
            )

        return (
            data,
            total_users,
            total_online,
            total_sent,
            total_decoded
        )

    def refresh_lists(self):
        if not self.online_list or not self.all_list:
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

            (
                users_data,
                total_users,
                total_online,
                total_sent,
                total_decoded
            ) = self.get_all_statistics()

            for item in users_data:
                text = (
                    item["username"]
                    + " | sent: "
                    + str(item["sent"])
                    + " | decoded: "
                    + str(item["decoded"])
                )

                self.all_list.insert(
                    tk.END,
                    text
                )

                if item["online"]:
                    self.online_list.insert(
                        tk.END,
                        text
                    )

            self.online_count_label.config(
                text=str(total_online)
            )

            self.registered_count_label.config(
                text=str(total_users)
            )

            self.sent_count_label.config(
                text=str(total_sent)
            )

            self.decoded_count_label.config(
                text=str(total_decoded)
            )

        self.root.after(
            0,
            refresh
        )

    def write_log(self, text):
        if not self.log_text:
            return

        def update():
            current_time = datetime.now().strftime(
                "%H:%M:%S"
            )

            self.log_text.config(
                state=tk.NORMAL
            )

            self.log_text.insert(
                tk.END,
                "[" + current_time + "] " + text + "\n"
            )

            self.log_text.config(
                state=tk.DISABLED
            )

            self.log_text.see(
                tk.END
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
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play()

        except Exception:
            pass

    def show_splash(self):
        splash = tk.Toplevel(
            self.root
        )

        splash.geometry(
            "450x250"
        )

        splash.resizable(
            False,
            False
        )

        splash.configure(
            bg="#20242b"
        )

        tk.Label(
            splash,
            text="MASKER",
            font=("Arial", 28, "bold"),
            fg="white",
            bg="#20242b"
        ).pack(
            pady=(45, 10)
        )

        tk.Label(
            splash,
            text="Lior Stas",
            font=("Arial", 16),
            fg="#dddddd",
            bg="#20242b"
        ).pack()

        tk.Label(
            splash,
            text="Cyber Security Project",
            font=("Arial", 10),
            fg="#aaaaaa",
            bg="#20242b"
        ).pack(
            pady=5
        )

        tk.Label(
            splash,
            text="Version 2.0",
            font=("Arial", 9),
            fg="#888888",
            bg="#20242b"
        ).pack()

        splash.after(
            2200,
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

        (
            users_data,
            total_users,
            total_online,
            total_sent,
            total_decoded
        ) = self.get_all_statistics()

        with open(
            path,
            "w",
            newline="",
            encoding="utf-8-sig"
        ) as file:

            writer = csv.writer(
                file
            )

            writer.writerow(
                [
                    "MASKER SERVER STATISTICS"
                ]
            )

            writer.writerow(
                [
                    "Generated",
                    datetime.now().strftime(
                        "%d/%m/%Y %H:%M:%S"
                    )
                ]
            )

            writer.writerow([])

            writer.writerow(
                [
                    "Username",
                    "Status",
                    "Files Sent",
                    "Decoded Files",
                    "Last Seen"
                ]
            )

            for item in users_data:
                if item["online"]:
                    status = "Online"

                elif item["last_seen"]:
                    status = "Offline"

                else:
                    status = "Never logged in"

                if item["last_seen"]:
                    last_seen = str(
                        item["last_seen"]
                    )

                else:
                    last_seen = "Never logged in"

                writer.writerow(
                    [
                        item["username"],
                        status,
                        item["sent"],
                        item["decoded"],
                        last_seen
                    ]
                )

            writer.writerow([])
            writer.writerow(["Summary"])
            writer.writerow(["Registered Users", total_users])
            writer.writerow(["Online Now", total_online])
            writer.writerow(["Total Files Sent", total_sent])
            writer.writerow(["Total Decoded", total_decoded])

        self.write_log(
            "Statistics exported"
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

    def create_stat_box(
        self,
        parent,
        title
    ):
        frame = tk.Frame(
            parent,
            bg="#2b3038",
            bd=1,
            relief="solid"
        )

        tk.Label(
            frame,
            text=title,
            font=("Arial", 10),
            fg="#bbbbbb",
            bg="#2b3038"
        ).pack(
            pady=(8, 2)
        )

        value = tk.Label(
            frame,
            text="0",
            font=("Arial", 18, "bold"),
            fg="white",
            bg="#2b3038"
        )

        value.pack(
            pady=(0, 8)
        )

        return frame, value

    def create_gui(self):
        self.play_audio()
        self.show_splash()

        self.root.deiconify()

        self.root.title(
            "MASKER Server"
        )

        self.root.geometry(
            "1000x700"
        )

        self.root.configure(
            bg="#1d2127"
        )

        title_frame = tk.Frame(
            self.root,
            bg="#1d2127"
        )

        title_frame.pack(
            fill="x",
            padx=20,
            pady=(18, 10)
        )

        tk.Label(
            title_frame,
            text="MASKER Server",
            font=("Arial", 22, "bold"),
            fg="white",
            bg="#1d2127"
        ).pack(
            side="left"
        )

        tk.Label(
            title_frame,
            text="Server Running",
            font=("Arial", 10),
            fg="#62c47b",
            bg="#1d2127"
        ).pack(
            side="right"
        )

        stats_frame = tk.Frame(
            self.root,
            bg="#1d2127"
        )

        stats_frame.pack(
            fill="x",
            padx=20,
            pady=(0, 10)
        )

        stats_frame.grid_columnconfigure(
            0,
            weight=1
        )

        stats_frame.grid_columnconfigure(
            1,
            weight=1
        )

        stats_frame.grid_columnconfigure(
            2,
            weight=1
        )

        stats_frame.grid_columnconfigure(
            3,
            weight=1
        )

        box, self.online_count_label = self.create_stat_box(
            stats_frame,
            "Online"
        )

        box.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=5
        )

        box, self.registered_count_label = self.create_stat_box(
            stats_frame,
            "Registered"
        )

        box.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=5
        )

        box, self.sent_count_label = self.create_stat_box(
            stats_frame,
            "Files Sent"
        )

        box.grid(
            row=0,
            column=2,
            sticky="nsew",
            padx=5
        )

        box, self.decoded_count_label = self.create_stat_box(
            stats_frame,
            "Decoded"
        )

        box.grid(
            row=0,
            column=3,
            sticky="nsew",
            padx=5
        )

        log_frame = tk.Frame(
            self.root,
            bg="#2b3038"
        )

        log_frame.pack(
            fill="both",
            padx=20,
            pady=8
        )

        tk.Label(
            log_frame,
            text="Server Log",
            font=("Arial", 13, "bold"),
            fg="white",
            bg="#2b3038"
        ).pack(
            anchor="w",
            padx=10,
            pady=(10, 5)
        )

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=10,
            bg="#181b20",
            fg="white",
            font=("Consolas", 10),
            state=tk.DISABLED
        )

        self.log_text.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 10)
        )

        clients_frame = tk.Frame(
            self.root,
            bg="#1d2127"
        )

        clients_frame.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=8
        )

        online_frame = tk.Frame(
            clients_frame,
            bg="#2b3038"
        )

        online_frame.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, 5)
        )

        tk.Label(
            online_frame,
            text="Connected Now",
            font=("Arial", 12, "bold"),
            fg="white",
            bg="#2b3038"
        ).pack(
            pady=8
        )

        self.online_list = tk.Listbox(
            online_frame,
            bg="#181b20",
            fg="white",
            font=("Consolas", 10)
        )

        self.online_list.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 10)
        )

        all_frame = tk.Frame(
            clients_frame,
            bg="#2b3038"
        )

        all_frame.pack(
            side="right",
            fill="both",
            expand=True,
            padx=(5, 0)
        )

        tk.Label(
            all_frame,
            text="All Clients",
            font=("Arial", 12, "bold"),
            fg="white",
            bg="#2b3038"
        ).pack(
            pady=8
        )

        self.all_list = tk.Listbox(
            all_frame,
            bg="#181b20",
            fg="white",
            font=("Consolas", 10)
        )

        self.all_list.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 10)
        )

        bottom_frame = tk.Frame(
            self.root,
            bg="#1d2127"
        )

        bottom_frame.pack(
            fill="x",
            padx=20,
            pady=(5, 15)
        )

        tk.Label(
            bottom_frame,
            text="Lior Stas | Version 2.0",
            font=("Arial", 9),
            fg="#999999",
            bg="#1d2127"
        ).pack(
            side="left"
        )

        
        tk.Button(
            bottom_frame,
            text="Export Statistics",
            command=self.export_statistics,
            width=18
        ).pack(
            side="right",
            padx=5
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