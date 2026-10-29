import os
import socket
import threading
import tkinter as tk

from tkinter import filedialog, messagebox, ttk

from constants import IP, PORT, BASE_DIR
from encrypt import Encryption


class Client:
    def __init__(self):
        self.sock = None
        self.encryptor = Encryption()
        self.username = ""
        self.busy = False
        self.closing = False

        self.bg = "#15191f"
        self.panel = "#20262e"
        self.input_bg = "#171c23"
        self.text = "#f0f3f6"
        self.muted = "#a7b0bd"
        self.accent = "#4caa9a"
        self.border = "#343d48"

        self.root = tk.Tk()
        self.root.title("VEIL | Client")
        self.root.geometry("950x680")
        self.root.minsize(760, 540)
        self.root.configure(bg=self.bg)
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)

        self.style = ttk.Style()
        self.style.theme_use("clam")

        self.style.configure(
            "Veil.TEntry",
            fieldbackground=self.input_bg,
            foreground=self.text,
            borderwidth=0,
            padding=8,
            font=("Segoe UI", 11)
        )

        self.main = tk.Frame(self.root, bg=self.bg)
        self.main.pack(fill="both", expand=True)

        self.activity_text = None

        self.show_login()

    def connect(self):
        self.close()

        sock = socket.socket()
        sock.settimeout(15)

        try:
            sock.connect((IP, PORT))
        except Exception:
            sock.close()
            raise

        sock.settimeout(None)
        self.sock = sock

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass

            self.sock = None

    def clear_page(self):
        for widget in self.main.winfo_children():
            widget.destroy()

        self.activity_text = None

    def create_label(
        self,
        parent,
        text,
        size=11,
        bold=False,
        color=None
    ):
        return tk.Label(
            parent,
            text=text,
            bg=parent.cget("bg"),
            fg=color or self.text,
            font=(
                "Segoe UI",
                size,
                "bold" if bold else "normal"
            )
        )

    def create_button(
        self,
        parent,
        text,
        command,
        primary=True,
        width=None
    ):
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=self.accent if primary else "#303943",
            fg="#10201e" if primary else self.text,
            activebackground="#6ac7b6" if primary else "#414d59",
            activeforeground="#10201e" if primary else self.text,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            padx=18,
            pady=11,
            cursor="hand2"
        )

        if width is not None:
            button.config(width=width)

        return button

    def create_header(self, logged_in=False):
        header = tk.Frame(self.main, bg=self.bg)

        header.pack(
            side="top",
            fill="x",
            padx=30,
            pady=(22, 12)
        )

        self.create_label(
            header,
            "VEIL",
            26,
            True
        ).pack(side="left")

        self.create_label(
            header,
            "SECURE MEDIA SYSTEM",
            10,
            True,
            self.muted
        ).pack(
            side="left",
            padx=18,
            pady=(11, 0)
        )

        if logged_in:
            self.create_button(
                header,
                "Logout",
                self.logout,
                primary=False,
                width=10
            ).pack(side="right")

            self.create_label(
                header,
                self.username,
                10,
                False,
                self.muted
            ).pack(
                side="right",
                padx=20
            )

        tk.Frame(
            self.main,
            bg=self.border,
            height=1
        ).pack(
            side="top",
            fill="x",
            padx=30
        )

    def create_footer(self):
        footer = tk.Frame(self.main, bg=self.bg)

        footer.pack(
            side="bottom",
            fill="x",
            padx=30,
            pady=(8, 18)
        )

        self.create_label(
            footer,
            "VEIL  |  Lior Stas  |  Version 2.0",
            9,
            False,
            self.muted
        ).pack(side="left")

    def run_task(self, task, callback):
        if self.busy or self.closing:
            return

        self.busy = True

        def worker():
            result = None
            error = None

            try:
                result = task()
            except Exception as exc:
                error = str(exc)

            def finish():
                if self.closing:
                    return

                self.busy = False

                if error is not None:
                    self.close()

                    messagebox.showerror(
                        "VEIL",
                        "Operation failed:\n" + error,
                        parent=self.root
                    )

                    self.show_login()
                    return

                callback(result)

            try:
                self.root.after(0, finish)
            except RuntimeError:
                pass

        threading.Thread(
            target=worker,
            daemon=True
        ).start()

    def create_auth_page(self, title, description):
        self.clear_page()
        self.create_header()
        self.create_footer()

        content = tk.Frame(self.main, bg=self.bg)

        content.pack(
            fill="both",
            expand=True,
            padx=25,
            pady=20
        )

        card = tk.Frame(
            content,
            bg=self.panel,
            highlightbackground=self.border,
            highlightthickness=1
        )

        card.place(
            relx=0.5,
            rely=0.5,
            anchor="center",
            width=440
        )

        self.create_label(
            card,
            title,
            22,
            True
        ).pack(
            anchor="w",
            padx=36,
            pady=(28, 4)
        )

        self.create_label(
            card,
            description,
            10,
            False,
            self.muted
        ).pack(
            anchor="w",
            padx=36,
            pady=(0, 20)
        )

        return card

    def create_field(self, parent, title, hidden=False):
        self.create_label(
            parent,
            title,
            10,
            True
        ).pack(
            anchor="w",
            padx=36,
            pady=(7, 6)
        )

        entry = ttk.Entry(
            parent,
            style="Veil.TEntry",
            show="*" if hidden else ""
        )

        entry.pack(
            fill="x",
            padx=36,
            pady=(0, 10),
            ipady=3
        )

        return entry

    def show_login(self):
        card = self.create_auth_page(
            "Welcome back",
            "Sign in to your account."
        )

        username = self.create_field(
            card,
            "Username"
        )

        password = self.create_field(
            card,
            "Password",
            hidden=True
        )

        status = self.create_label(
            card,
            "",
            9,
            False,
            "#ed8585"
        )

        status.pack(
            anchor="w",
            padx=36,
            pady=(2, 0)
        )

        def submit():
            if self.busy:
                return

            name = username.get().strip()
            secret = password.get()

            if not name or not secret:
                status.config(
                    text="Please enter your username and password."
                )
                return

            status.config(
                text="Signing in...",
                fg=self.muted
            )

            self.run_task(
                lambda: self.perform_login(name, secret),
                self.login_finished
            )

        self.create_button(
            card,
            "Sign In",
            submit
        ).pack(
            fill="x",
            padx=36,
            pady=(16, 9)
        )

        self.create_button(
            card,
            "Create an Account",
            self.show_register,
            primary=False
        ).pack(
            fill="x",
            padx=36,
            pady=(0, 28)
        )

        username.bind(
            "<Return>",
            lambda event: password.focus_set()
        )

        password.bind(
            "<Return>",
            lambda event: submit()
        )

        username.focus_set()

    def show_register(self):
        if self.busy:
            return

        card = self.create_auth_page(
            "Create account",
            "Create your VEIL account."
        )

        username = self.create_field(
            card,
            "Username"
        )

        password = self.create_field(
            card,
            "Password",
            hidden=True
        )

        confirm = self.create_field(
            card,
            "Confirm Password",
            hidden=True
        )

        status = self.create_label(
            card,
            "",
            9,
            False,
            "#ed8585"
        )

        status.pack(
            anchor="w",
            padx=36,
            pady=(0, 0)
        )

        def submit():
            if self.busy:
                return

            name = username.get().strip()
            secret = password.get()

            if len(name) < 3:
                status.config(
                    text="Username must be at least 3 characters."
                )
                return

            if len(secret) < 4:
                status.config(
                    text="Password must be at least 4 characters."
                )
                return

            if secret != confirm.get():
                status.config(
                    text="Passwords do not match."
                )
                return

            status.config(
                text="Creating account...",
                fg=self.muted
            )

            self.run_task(
                lambda: self.perform_register(name, secret),
                self.register_finished
            )

        self.create_button(
            card,
            "Create Account",
            submit
        ).pack(
            fill="x",
            padx=36,
            pady=(12, 9)
        )

        self.create_button(
            card,
            "Back to Login",
            self.show_login,
            primary=False
        ).pack(
            fill="x",
            padx=36,
            pady=(0, 25)
        )

        username.bind(
            "<Return>",
            lambda event: password.focus_set()
        )

        password.bind(
            "<Return>",
            lambda event: confirm.focus_set()
        )

        confirm.bind(
            "<Return>",
            lambda event: submit()
        )

        username.focus_set()

    def perform_register(self, username, password):
        self.connect()

        try:
            self.encryptor.send_encrypted_message(
                self.sock,
                "REGISTER"
            )

            self.encryptor.send_encrypted_message(
                self.sock,
                username
            )

            self.encryptor.send_encrypted_message(
                self.sock,
                password
            )

            return self.encryptor.receive_encrypted_message(
                self.sock
            )

        finally:
            self.close()

    def register_finished(self, result):
        if result == "REGISTER_OK":
            messagebox.showinfo(
                "Registration",
                "Account created successfully.\n"
                "You can now sign in.",
                parent=self.root
            )

            self.show_login()

        else:
            messagebox.showerror(
                "Registration",
                result,
                parent=self.root
            )

    def perform_login(self, username, password):
        self.connect()

        self.encryptor.send_encrypted_message(
            self.sock,
            "LOGIN"
        )

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

        if result != "LOGIN_OK":
            self.close()

        return result, username

    def login_finished(self, result):
        answer, username = result

        if answer == "LOGIN_OK":
            self.username = username
            self.show_dashboard()

        else:
            messagebox.showerror(
                "Login",
                answer,
                parent=self.root
            )

    def create_action_card(
        self,
        parent,
        title,
        description,
        button_text,
        command
    ):
        card = tk.Frame(
            parent,
            bg=self.panel,
            highlightbackground=self.border,
            highlightthickness=1
        )

        self.create_label(
            card,
            title,
            17,
            True
        ).pack(
            anchor="w",
            padx=24,
            pady=(22, 6)
        )

        self.create_label(
            card,
            description,
            10,
            False,
            self.muted
        ).pack(
            anchor="w",
            padx=24,
            pady=(0, 15)
        )

        self.create_button(
            card,
            button_text,
            command,
            width=15
        ).pack(
            anchor="w",
            padx=24,
            pady=(0, 22)
        )

        return card

    def show_dashboard(self):
        self.clear_page()

        self.create_header(logged_in=True)
        self.create_footer()

        content = tk.Frame(self.main, bg=self.bg)

        content.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=20
        )

        self.create_label(
            content,
            "Dashboard",
            22,
            True
        ).pack(
            anchor="w",
            pady=(0, 3)
        )

        self.create_label(
            content,
            "Choose an action to get started.",
            10,
            False,
            self.muted
        ).pack(
            anchor="w",
            pady=(0, 20)
        )

        actions = tk.Frame(content, bg=self.bg)

        actions.pack(
            fill="x",
            pady=(0, 16)
        )

        hide_card = self.create_action_card(
            actions,
            "Hide Data",
            "Hide an image inside a cover file.",
            "Select File",
            self.prepare_hide
        )

        hide_card.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, 7)
        )

        decode_card = self.create_action_card(
            actions,
            "Decode Data",
            "Extract hidden images from a file.",
            "Choose File",
            self.prepare_decode
        )

        decode_card.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(7, 0)
        )

        activity_frame = tk.Frame(
            content,
            bg=self.panel,
            highlightbackground=self.border,
            highlightthickness=1
        )

        activity_frame.pack(
            fill="both",
            expand=True
        )

        self.create_label(
            activity_frame,
            "Activity",
            13,
            True
        ).pack(
            anchor="w",
            padx=18,
            pady=(13, 8)
        )

        self.activity_text = tk.Text(
            activity_frame,
            bg=self.input_bg,
            fg=self.text,
            insertbackground=self.text,
            font=("Consolas", 10),
            relief="flat",
            state="disabled",
            height=5,
            padx=10,
            pady=10
        )

        self.activity_text.pack(
            fill="both",
            expand=True,
            padx=18,
            pady=(0, 15)
        )

        self.add_activity("Connected successfully.")

    def add_activity(self, message):
        if self.closing:
            return

        def update():
            if self.activity_text is None:
                return

            try:
                self.activity_text.config(state="normal")
                self.activity_text.insert(
                    "end",
                    message + "\n"
                )
                self.activity_text.config(state="disabled")
                self.activity_text.see("end")

            except tk.TclError:
                pass

        try:
            self.root.after(0, update)
        except RuntimeError:
            pass

    def prepare_hide(self):
        if self.busy:
            return

        self.add_activity("Loading available media...")

        self.run_task(
            self.request_hide_menu,
            self.choose_hide_media
        )

    def request_hide_menu(self):
        self.encryptor.send_encrypted_message(
            self.sock,
            "1"
        )

        return self.encryptor.receive_encrypted_message(
            self.sock
        )

    def choose_hide_media(self, menu):
        if menu == "NO_MEDIA":
            messagebox.showwarning(
                "Hide Data",
                "No cover media is available.",
                parent=self.root
            )
            return

        window = tk.Toplevel(self.root)

        window.title("VEIL | Select Cover")
        window.geometry("430x320")
        window.resizable(False, False)
        window.configure(bg=self.bg)
        window.transient(self.root)
        window.grab_set()

        self.create_label(
            window,
            "Select a cover image",
            17,
            True
        ).pack(
            anchor="w",
            padx=28,
            pady=(24, 7)
        )

        self.create_label(
            window,
            "Available media:",
            10,
            False,
            self.muted
        ).pack(
            anchor="w",
            padx=28
        )

        options = []

        for line in menu.splitlines():
            if ":" in line:
                media_id, name = line.split(":", 1)
                options.append(
                    (media_id.strip(), name.strip())
                )

        if not options:
            window.destroy()

            self.run_task(
                lambda: self.cancel_hide(),
                lambda result: None
            )
            return

        selected = tk.StringVar(
            value=options[0][0]
        )

        for media_id, name in options:
            tk.Radiobutton(
                window,
                text=media_id + " - " + name,
                variable=selected,
                value=media_id,
                bg=self.bg,
                fg=self.text,
                selectcolor=self.panel,
                activebackground=self.bg,
                activeforeground=self.text,
                font=("Segoe UI", 11),
                anchor="w"
            ).pack(
                fill="x",
                padx=28,
                pady=5
            )

        buttons = tk.Frame(
            window,
            bg=self.bg
        )

        buttons.pack(
            side="bottom",
            fill="x",
            padx=28,
            pady=23
        )

        def cancel():
            window.destroy()

            self.run_task(
                self.cancel_hide,
                lambda result: self.add_activity(
                    "Hide operation cancelled."
                )
            )

        def continue_hide():
            media_id = selected.get()
            window.destroy()

            file_path = filedialog.askopenfilename(
                parent=self.root,
                title="Choose the image to hide",
                filetypes=[
                    ("JPEG images", "*.jpg *.jpeg"),
                    ("All files", "*.*")
                ]
            )

            self.run_task(
                lambda: self.perform_hide(media_id, file_path),
                self.hide_finished
            )

        self.create_button(
            buttons,
            "Cancel",
            cancel,
            primary=False,
            width=11
        ).pack(side="left")

        self.create_button(
            buttons,
            "Continue",
            continue_hide,
            width=11
        ).pack(side="right")

        window.protocol(
            "WM_DELETE_WINDOW",
            cancel
        )

    def cancel_hide(self):
        self.encryptor.send_encrypted_message(
            self.sock,
            "0"
        )

        return self.encryptor.receive_encrypted_message(
            self.sock
        )

    def perform_hide(self, media_id, file_path):
        self.encryptor.send_encrypted_message(
            self.sock,
            media_id
        )

        answer = self.encryptor.receive_encrypted_message(
            self.sock
        )

        if answer != "MEDIA_OK":
            return answer

        if not file_path or not os.path.isfile(file_path):
            self.encryptor.send_encrypted_bytes(
                self.sock,
                b""
            )

            self.encryptor.receive_encrypted_message(
                self.sock
            )

            return "CANCELLED"

        with open(file_path, "rb") as file:
            data = file.read()

        self.encryptor.send_encrypted_bytes(
            self.sock,
            data
        )

        return self.encryptor.receive_encrypted_message(
            self.sock
        )

    def hide_finished(self, result):
        if result == "CANCELLED":
            self.add_activity("Hide operation cancelled.")
            return

        if result.startswith("OK:"):
            self.add_activity(result)

            messagebox.showinfo(
                "Hide Data",
                "Image hidden successfully.\n\n"
                + result[3:],
                parent=self.root
            )

        else:
            self.add_activity(result)

            messagebox.showerror(
                "Hide Data",
                result,
                parent=self.root
            )

    def prepare_decode(self):
        if self.busy:
            return

        output_dir = os.path.join(
            BASE_DIR,
            "output"
        )

        initial_dir = (
            output_dir
            if os.path.isdir(output_dir)
            else BASE_DIR
        )

        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="Choose a file to decode",
            initialdir=initial_dir,
            filetypes=[
                ("JPEG images", "*.jpg *.jpeg"),
                ("All files", "*.*")
            ]
        )

        if not file_path:
            return

        self.add_activity(
            "Decoding: " + os.path.basename(file_path)
        )

        self.run_task(
            lambda: self.perform_decode(file_path),
            self.decode_finished
        )

    def perform_decode(self, file_path):
        self.encryptor.send_encrypted_message(
            self.sock,
            "2"
        )

        if os.path.isfile(file_path):
            with open(file_path, "rb") as file:
                data = file.read()
        else:
            data = b""

        self.encryptor.send_encrypted_bytes(
            self.sock,
            data
        )

        amount_text = self.encryptor.receive_encrypted_message(
            self.sock
        )

        amount = int(amount_text) if amount_text else 0

        output_dir = os.path.join(
            BASE_DIR,
            "client_decoded"
        )

        os.makedirs(
            output_dir,
            exist_ok=True
        )

        saved = []

        for index in range(amount):
            server_path = self.encryptor.receive_encrypted_message(
                self.sock
            )

            image_data = self.encryptor.receive_encrypted_bytes(
                self.sock
            )

            file_name = os.path.basename(
                server_path.replace("\\", "/")
            )

            save_path = os.path.join(
                output_dir,
                file_name
            )

            with open(save_path, "wb") as file:
                file.write(image_data)

            saved.append(save_path)

        return amount, saved, output_dir

    def decode_finished(self, result):
        amount, saved, output_dir = result

        self.add_activity(
            "Decode complete. Found: " + str(amount)
        )

        for path in saved:
            self.add_activity("Saved: " + path)

        if amount > 0:
            message = (
                str(amount)
                + " image(s) extracted successfully.\n\n"
                + "Saved in:\n"
                + output_dir
            )

        else:
            message = "No hidden images were found."

        messagebox.showinfo(
            "Decode Data",
            message,
            parent=self.root
        )

    def logout(self):
        if self.busy:
            messagebox.showwarning(
                "VEIL",
                "Please wait for the current operation to finish.",
                parent=self.root
            )
            return

        self.run_task(
            self.perform_logout,
            self.logout_finished
        )

    def perform_logout(self):
        try:
            if self.sock:
                self.encryptor.send_encrypted_message(
                    self.sock,
                    "3"
                )
        finally:
            self.close()

    def logout_finished(self, result):
        self.username = ""
        self.show_login()

    def exit_app(self):
        if self.closing:
            return

        self.closing = True
        self.close()

        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    Client().run()