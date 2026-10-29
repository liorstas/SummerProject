import csv
import hashlib
import os
import socket
import threading
import tkinter as tk

from datetime import datetime
from tkinter import ttk, messagebox, scrolledtext

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

        self.db.create_database(DB_CONFIG["database"])
        self.db.reconnect(DB_CONFIG["database"])

        create_all_tables(self.db)
        populate_media_menu(self.db)
        fix_old_paths(self.db)

        self.db.execute("UPDATE users SET is_online = 0")

        self.encryptor = Encryption()

        self.root = tk.Tk()
        self.root.withdraw()

        self.bg = "#15191f"
        self.panel = "#20262e"
        self.input_bg = "#171c23"
        self.text = "#f0f3f6"
        self.muted = "#a7b0bd"
        self.accent = "#4caa9a"
        self.border = "#343d48"

        self.log_text = None
        self.online_table = None
        self.users_table = None

        self.online_count = None
        self.registered_count = None
        self.sent_count = None
        self.decoded_count = None

        self.status_label = None
        self.server_socket = None
        self.running = True

        self.root.protocol("WM_DELETE_WINDOW", self.close_server)

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

        username_hash = self.get_hash(username.lower())
        password_hash = self.get_hash(password)

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

        self.write_log("Registered: " + username)
        self.refresh_lists()

    def login_user(self, sock):
        username = self.encryptor.receive_encrypted_message(
            sock
        ).strip()

        password = self.encryptor.receive_encrypted_message(
            sock
        )

        username_hash = self.get_hash(username.lower())
        password_hash = self.get_hash(password)

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

        return username_hash, user[1]

    def connect_client(self, client_id, username, address):
        self.db.update_row(
            "users",
            "username_hash",
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

    def add_stat(self, client_id, column):
        if column not in (
            "total_sent_media",
            "total_decoded_media"
        ):
            return

        self.db.execute(
            "UPDATE users SET "
            + column
            + " = COALESCE("
            + column
            + ", 0) + 1 WHERE username_hash = %s",
            (client_id,)
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

            result = self.login_user(sock)

            if not result:
                return

            client_id, username = result

            self.connect_client(
                client_id,
                username,
                address
            )

            self.write_log(username + " connected")
            self.refresh_lists()

            while self.running:
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
            pass

        except Exception as error:
            self.write_log("Client error: " + str(error))

        finally:
            if client_id:
                try:
                    self.db.update_row(
                        "users",
                        "username_hash",
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
                except Exception as error:
                    self.write_log(
                        "Database error: " + str(error)
                    )

                self.write_log(username + " disconnected")
                self.refresh_lists()

            try:
                sock.close()
            except OSError:
                pass

    def get_all_statistics(self):
        users = self.db.get_all_rows("users")

        data = []
        total_online = 0
        total_sent = 0
        total_decoded = 0

        for user in users:
            username = user[1]
            ip = user[3] or "-"
            last_seen = user[5]
            online = bool(user[7])
            sent = user[8] or 0
            decoded = user[9] or 0

            if online:
                total_online += 1

            total_sent += sent
            total_decoded += decoded

            data.append(
                {
                    "username": username,
                    "ip": ip,
                    "online": online,
                    "sent": sent,
                    "decoded": decoded,
                    "last_seen": last_seen
                }
            )

        return (
            data,
            len(users),
            total_online,
            total_sent,
            total_decoded
        )

    def refresh_lists(self):
        if self.online_table is None or self.users_table is None:
            return

        def refresh():
            if not self.running:
                return

            try:
                (
                    data,
                    registered,
                    online,
                    sent,
                    decoded
                ) = self.get_all_statistics()

                for table in (self.online_table, self.users_table):
                    for row in table.get_children():
                        table.delete(row)

                for item in data:
                    if item["online"]:
                        status = "Online"
                    elif item["last_seen"]:
                        status = "Offline"
                    else:
                        status = "Never logged in"

                    last_seen = (
                        str(item["last_seen"])
                        if item["last_seen"]
                        else "Never"
                    )

                    values = (
                        item["username"],
                        status,
                        item["ip"],
                        item["sent"],
                        item["decoded"],
                        last_seen
                    )

                    self.users_table.insert(
                        "",
                        "end",
                        values=values
                    )

                    if item["online"]:
                        self.online_table.insert(
                            "",
                            "end",
                            values=values
                        )

                self.online_count.config(text=str(online))
                self.registered_count.config(text=str(registered))
                self.sent_count.config(text=str(sent))
                self.decoded_count.config(text=str(decoded))

            except Exception as error:
                self.write_log("Refresh error: " + str(error))

        self.root.after(0, refresh)

    def write_log(self, message):
        if self.log_text is None:
            return

        def update():
            if not self.running:
                return

            try:
                time = datetime.now().strftime("%H:%M:%S")

                self.log_text.config(state="normal")
                self.log_text.insert(
                    "end",
                    "[" + time + "] " + message + "\n"
                )
                self.log_text.config(state="disabled")
                self.log_text.see("end")

            except tk.TclError:
                pass

        self.root.after(0, update)

    def play_audio(self):
        path = os.path.join(
            BASE_DIR,
            "lior_intro.wav"
        )

        if not os.path.exists(path):
            return

        try:
            pygame.mixer.init()
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
        except Exception:
            pass

    def show_splash(self):
        splash = tk.Toplevel(self.root)

        splash.title("VEIL")
        splash.geometry("460x255")
        splash.resizable(False, False)
        splash.configure(bg=self.bg)

        tk.Frame(
            splash,
            bg=self.accent,
            height=4
        ).pack(fill="x")

        tk.Label(
            splash,
            text="VEIL",
            bg=self.bg,
            fg=self.text,
            font=("Segoe UI", 34, "bold")
        ).pack(pady=(43, 5))

        tk.Label(
            splash,
            text="Secure Media System",
            bg=self.bg,
            fg=self.muted,
            font=("Segoe UI", 12)
        ).pack()

        tk.Label(
            splash,
            text="Lior Stas  |  Version 2.0",
            bg=self.bg,
            fg=self.muted,
            font=("Segoe UI", 9)
        ).pack(pady=28)

        splash.after(1600, splash.destroy)
        self.root.wait_window(splash)

    def export_statistics(self):
        try:
            path = os.path.join(
                BASE_DIR,
                "server_statistics.csv"
            )

            (
                data,
                registered,
                online,
                sent,
                decoded
            ) = self.get_all_statistics()

            with open(
                path,
                "w",
                newline="",
                encoding="utf-8-sig"
            ) as file:
                writer = csv.writer(file)

                writer.writerow(["VEIL SERVER STATISTICS"])

                writer.writerow([
                    "Generated",
                    datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                ])

                writer.writerow([])

                writer.writerow([
                    "Username",
                    "Status",
                    "IP",
                    "Files Sent",
                    "Decoded Files",
                    "Last Seen"
                ])

                for item in data:
                    if item["online"]:
                        status = "Online"
                    elif item["last_seen"]:
                        status = "Offline"
                    else:
                        status = "Never logged in"

                    writer.writerow([
                        item["username"],
                        status,
                        item["ip"],
                        item["sent"],
                        item["decoded"],
                        str(item["last_seen"])
                        if item["last_seen"]
                        else "Never"
                    ])

                writer.writerow([])
                writer.writerow(["SUMMARY"])
                writer.writerow(["Registered Users", registered])
                writer.writerow(["Online Users", online])
                writer.writerow(["Total Files Sent", sent])
                writer.writerow(["Total Decoded", decoded])

            self.write_log("Statistics exported")

            messagebox.showinfo(
                "Export Complete",
                "Statistics saved to:\n" + path
            )

        except Exception as error:
            messagebox.showerror(
                "Export Failed",
                str(error)
            )

    def start_server(self):
        try:
            self.server_socket = socket.socket()

            self.server_socket.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_REUSEADDR,
                1
            )

            self.server_socket.bind((IP, PORT))
            self.server_socket.listen()

            self.write_log(
                "Server started on " + IP + ":" + str(PORT)
            )

            self.root.after(
                0,
                lambda: self.status_label.config(
                    text="Server running",
                    fg=self.accent
                )
            )

            while self.running:
                try:
                    sock, address = self.server_socket.accept()
                except OSError:
                    break

                threading.Thread(
                    target=self.handle_client,
                    args=(sock, address),
                    daemon=True
                ).start()

        except Exception as error:
            self.write_log("Server error: " + str(error))

            self.root.after(
                0,
                lambda: self.status_label.config(
                    text="Server error",
                    fg="#e27777"
                )
            )

    def create_stat_card(self, parent, title):
        frame = tk.Frame(
            parent,
            bg=self.panel,
            highlightbackground=self.border,
            highlightthickness=1
        )

        tk.Label(
            frame,
            text=title,
            bg=self.panel,
            fg=self.muted,
            font=("Segoe UI", 10)
        ).pack(
            anchor="w",
            padx=17,
            pady=(10, 2)
        )

        value = tk.Label(
            frame,
            text="0",
            bg=self.panel,
            fg=self.text,
            font=("Segoe UI", 20, "bold")
        )

        value.pack(
            anchor="w",
            padx=17,
            pady=(0, 8)
        )

        return frame, value

    def create_table(self, parent):
        columns = (
            "Username",
            "Status",
            "IP",
            "Sent",
            "Decoded",
            "Last Seen"
        )

        frame = tk.Frame(parent, bg=self.panel)

        table = ttk.Treeview(
            frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=4
        )

        widths = {
            "Username": 145,
            "Status": 125,
            "IP": 125,
            "Sent": 70,
            "Decoded": 85,
            "Last Seen": 170
        }

        for column in columns:
            table.heading(column, text=column)
            table.column(
                column,
                width=widths[column],
                minwidth=55,
                stretch=True,
                anchor="w"
            )

        scrollbar = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=table.yview
        )

        table.configure(
            yscrollcommand=scrollbar.set
        )

        scrollbar.pack(
            side="right",
            fill="y"
        )

        table.pack(
            side="left",
            fill="both",
            expand=True
        )

        return frame, table

    def create_section(self, parent, title):
        section = tk.Frame(
            parent,
            bg=self.panel,
            highlightbackground=self.border,
            highlightthickness=1
        )

        tk.Label(
            section,
            text=title,
            bg=self.panel,
            fg=self.text,
            font=("Segoe UI", 12, "bold")
        ).pack(
            anchor="w",
            padx=14,
            pady=(9, 5)
        )

        return section

    def close_server(self):
        self.running = False

        if self.server_socket:
            try:
                self.server_socket.close()
            except OSError:
                pass

        self.root.destroy()

    def create_gui(self):
        self.play_audio()
        self.show_splash()

        self.root.deiconify()
        self.root.title("VEIL | Server")

        self.root.geometry("1120x720")
        self.root.minsize(850, 550)
        self.root.configure(bg=self.bg)

        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Treeview",
            background=self.input_bg,
            foreground=self.text,
            fieldbackground=self.input_bg,
            rowheight=27,
            font=("Segoe UI", 10),
            borderwidth=0
        )

        style.configure(
            "Treeview.Heading",
            background="#303946",
            foreground=self.text,
            font=("Segoe UI", 10, "bold"),
            padding=6
        )

        style.map(
            "Treeview",
            background=[("selected", self.accent)],
            foreground=[("selected", "white")]
        )

        # The footer is packed first and stays at the bottom.
        footer = tk.Frame(self.root, bg=self.bg)
        footer.pack(
            side="bottom",
            fill="x",
            padx=22,
            pady=(6, 12)
        )

        tk.Label(
            footer,
            text="VEIL  |  Lior Stas  |  Version 2.0",
            bg=self.bg,
            fg=self.muted,
            font=("Segoe UI", 9)
        ).pack(side="left")

        tk.Button(
            footer,
            text="Export Statistics",
            command=self.export_statistics,
            bg=self.accent,
            fg="#10201e",
            activebackground="#69c7b7",
            activeforeground="#10201e",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            padx=20,
            pady=9,
            cursor="hand2"
        ).pack(side="right")

        # The log is packed second, directly above the footer.
        log_section = tk.Frame(
            self.root,
            bg=self.panel,
            highlightbackground=self.border,
            highlightthickness=1
        )

        log_section.pack(
            side="bottom",
            fill="x",
            padx=22,
            pady=(5, 0)
        )

        tk.Label(
            log_section,
            text="Server activity",
            bg=self.panel,
            fg=self.text,
            font=("Segoe UI", 12, "bold")
        ).pack(
            anchor="w",
            padx=12,
            pady=(8, 4)
        )

        self.log_text = scrolledtext.ScrolledText(
            log_section,
            height=3,
            bg=self.input_bg,
            fg=self.text,
            insertbackground=self.text,
            font=("Consolas", 9),
            relief="flat",
            state="disabled",
            padx=8,
            pady=6
        )

        self.log_text.pack(
            fill="x",
            padx=12,
            pady=(0, 9)
        )

        # Header and statistics stay at the top.
        header = tk.Frame(self.root, bg=self.bg)
        header.pack(
            side="top",
            fill="x",
            padx=22,
            pady=(14, 9)
        )

        tk.Label(
            header,
            text="VEIL",
            bg=self.bg,
            fg=self.text,
            font=("Segoe UI", 24, "bold")
        ).pack(side="left")

        tk.Label(
            header,
            text="SERVER DASHBOARD",
            bg=self.bg,
            fg=self.muted,
            font=("Segoe UI", 10)
        ).pack(
            side="left",
            padx=15,
            pady=(8, 0)
        )

        self.status_label = tk.Label(
            header,
            text="Starting server...",
            bg=self.bg,
            fg=self.muted,
            font=("Segoe UI", 10, "bold")
        )

        self.status_label.pack(side="right")

        stats = tk.Frame(self.root, bg=self.bg)
        stats.pack(
            side="top",
            fill="x",
            padx=16,
            pady=(0, 9)
        )

        for column in range(4):
            stats.grid_columnconfigure(
                column,
                weight=1,
                uniform="stats"
            )

        cards = [
            ("Online users", "online_count"),
            ("Registered users", "registered_count"),
            ("Files sent", "sent_count"),
            ("Decoded files", "decoded_count")
        ]

        for index, (title, name) in enumerate(cards):
            card, value = self.create_stat_card(
                stats,
                title
            )

            card.grid(
                row=0,
                column=index,
                sticky="ew",
                padx=5
            )

            setattr(self, name, value)

        # Only this area expands when the window is resized.
        middle = tk.Frame(self.root, bg=self.bg)
        middle.pack(
            side="top",
            fill="both",
            expand=True,
            padx=22,
            pady=(0, 5)
        )

        middle.grid_columnconfigure(0, weight=1)
        middle.grid_rowconfigure(0, weight=1, uniform="tables")
        middle.grid_rowconfigure(1, weight=1, uniform="tables")

        online_section = self.create_section(
            middle,
            "Connected now"
        )

        online_section.grid(
            row=0,
            column=0,
            sticky="nsew",
            pady=(0, 4)
        )

        online_table_frame, self.online_table = self.create_table(
            online_section
        )

        online_table_frame.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=(0, 9)
        )

        users_section = self.create_section(
            middle,
            "All users"
        )

        users_section.grid(
            row=1,
            column=0,
            sticky="nsew",
            pady=(4, 0)
        )

        users_table_frame, self.users_table = self.create_table(
            users_section
        )

        users_table_frame.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=(0, 9)
        )

        self.refresh_lists()

        threading.Thread(
            target=self.start_server,
            daemon=True
        ).start()

        self.root.mainloop()


if __name__ == "__main__":
    Server().create_gui()