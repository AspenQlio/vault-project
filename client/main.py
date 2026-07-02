import customtkinter as ctk
from tkinter import messagebox
import ctypes
import os
import secrets
import requests
import hashlib
import json
import string
import sqlite3

SERVER_URL = "https://api-vault-cfd6.onrender.com"

def automatic_cloud_download(username, user_id, db_path="vault_local.db", server_url=SERVER_URL):
    print(f"\n Downloading cloud credentials for user: {username}...")
    try:
        response = requests.get(f"{server_url}/api/sync/{username}", timeout=5)
        if response.status_code == 200:
            payload = response.json()
            cloud_credentials = payload.get("credentials", payload if isinstance(payload, list) else [])
            
            if not cloud_credentials:
                print("󰆧 You don't have any passwords saved in the cloud yet.")
                return
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            new_downloads = 0
            
            for cred in cloud_credentials:
                nonce = cred.get("nonce_hex")
                crypto_pass = cred.get("encrypted_data_hex") or cred.get("datos_cifrados_hex")
                
                if not nonce or not crypto_pass:
                    continue

                cursor.execute("SELECT id FROM local_credentials WHERE user_id = ? AND nonce_hex = ?", (user_id, nonce))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO local_credentials (user_id, nonce_hex, encrypted_data_hex, estado)
                        VALUES (?, ?, ?, 'Cloud')
                    """, (user_id, nonce, crypto_pass))
                    new_downloads += 1
            
            conn.commit()
            conn.close()
            
            if new_downloads > 0:
                print(f" Sync complete! Downloaded {new_downloads} passwords from the cloud.")
            else:
                print(" Everything is up to date.")
    except Exception as e:
        print(f" Error during automatic download: {e}")

def load_crypto_core():
    current_path = os.path.dirname(os.path.abspath(__file__))
    lib_path = os.path.join(current_path, "../core_crypto/libvault_crypto.so")
    core_lib = ctypes.CDLL(lib_path)
    core_lib.inicializar_motor.restype = ctypes.c_int
    core_lib.cifrar_credencial.argtypes = [ctypes.c_char_p, ctypes.c_ulonglong, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
    core_lib.cifrar_credencial.restype = ctypes.c_int
    core_lib.descifrar_credencial.argtypes = [ctypes.c_char_p, ctypes.c_ulonglong, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
    core_lib.descifrar_credencial.restype = ctypes.c_int
    return core_lib

class VaultApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Vault - Zero Knowledge (Hybrid Architecture)")
        self.geometry("950x650")
        self.minsize(850, 600)
        self.icon_font = ("JetBrainsMono Nerd Font", 14)
        self.icon_title_font = ("JetBrainsMono Nerd Font", 24, "bold")
        self.icon_button_font = ("JetBrainsMono Nerd Font", 13)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.core = load_crypto_core()
        if self.core.inicializar_motor() < 0:
            print(" Fatal error with libsodium.")
            self.destroy()
            
        self.symmetric_key = None
        self.current_user = None
        self.inactivity_id = None
        
        # Variables for Password Generator
        self.gen_len = ctk.IntVar(value=16)
        self.gen_upper = ctk.BooleanVar(value=True)
        self.gen_nums = ctk.BooleanVar(value=True)
        self.gen_syms = ctk.BooleanVar(value=True)
        
        self.bind("<Any-KeyPress>", self.reset_inactivity_timer)
        self.bind("<Any-Motion>", self.reset_inactivity_timer)
        self.bind("<Any-Button>", self.reset_inactivity_timer)
        
        self.initialize_local_db()
        self.show_welcome_screen()

    def reset_inactivity_timer(self, event=None):
        if not self.current_user:
            return
        if self.inactivity_id is not None:
            self.after_cancel(self.inactivity_id)
        self.inactivity_id = self.after(60000, self.lock_vault)

    def lock_vault(self):
        self.current_user = None
        self.symmetric_key = None
        self.clipboard_clear()
        if self.inactivity_id is not None:
            self.after_cancel(self.inactivity_id)
            self.inactivity_id = None
        print(" Vault locked for security reasons.")
        self.show_welcome_screen()

    def initialize_local_db(self):
        connection = sqlite3.connect("vault_local.db")
        cursor = connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS local_credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                nonce_hex TEXT,
                encrypted_data_hex TEXT
            )
        ''')
        cursor.execute("PRAGMA table_info(local_credentials)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        for column_name, column_type in (
            ("sitio", "TEXT"),
            ("usuario_crypto", "TEXT"),
            ("pass_crypto", "TEXT"),
            ("estado", "TEXT DEFAULT 'Local'"),
        ):
            if column_name not in existing_columns:
                cursor.execute(f"ALTER TABLE local_credentials ADD COLUMN {column_name} {column_type}")
        connection.commit()
        connection.close()

    def clear_screen(self):
        for widget in self.winfo_children():
            widget.destroy()

    def process_keys(self, password):
        auth_hash = hashlib.sha256((password + "auth_salt").encode('utf-8')).hexdigest()
        encryption_key = hashlib.sha256((password + "enc_salt").encode('utf-8')).digest()
        return auth_hash, encryption_key

    def show_welcome_screen(self):
        self.clear_screen()
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        login_frame = ctk.CTkFrame(self, fg_color="transparent")
        login_frame.grid(row=0, column=0)
        
        ctk.CTkLabel(login_frame, text="󰌾", font=self.icon_title_font).pack(pady=(0, 10))
        ctk.CTkLabel(login_frame, text="Vault Authentication", font=("Roboto", 24, "bold")).pack(pady=(0, 30))
        
        self.entry_user = ctk.CTkEntry(login_frame, placeholder_text="Username", width=350, height=45)
        self.entry_user.pack(pady=(0, 15))
        
        self.entry_pwd = ctk.CTkEntry(login_frame, placeholder_text="Master Password", show="•", width=350, height=45)
        self.entry_pwd.pack(pady=(0, 20))
        
        self.lbl_error = ctk.CTkLabel(login_frame, text="", text_color="#ff4a4a")
        self.lbl_error.pack(pady=(0, 10))
        
        button_frame = ctk.CTkFrame(login_frame, fg_color="transparent")
        button_frame.pack()
        
        ctk.CTkButton(button_frame, text="Login", command=self.login, width=170, height=40, font=("Roboto", 14, "bold")).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Create Account", command=self.register, width=170, height=40, fg_color="#3b3b3b", hover_color="#555555").pack(side="left", padx=5)

    def register(self):
        username = self.entry_user.get()
        password = self.entry_pwd.get()
        if not username or not password:
            self.lbl_error.configure(text="Please fill in both fields.", text_color="#ff4a4a")
            return
        auth_hash, _ = self.process_keys(password)
        try:
            res = requests.post(f"{SERVER_URL}/api/register", json={"username": username, "auth_hash": auth_hash})
            if res.status_code == 200:
                self.lbl_error.configure(text="Account created! Please log in.", text_color="#4aff6b")
            else:
                self.lbl_error.configure(text="Username already exists.", text_color="#ff4a4a")
        except requests.exceptions.ConnectionError:
            self.lbl_error.configure(text="Network error.", text_color="#ff4a4a")

    def login(self):
        username = self.entry_user.get()
        password = self.entry_pwd.get()
        if not username or not password:
            self.lbl_error.configure(text="Please fill in both fields.", text_color="#ff4a4a")
            return
        
        auth_hash, encryption_key = self.process_keys(password)
        try:
            res = requests.post(f"{SERVER_URL}/api/login", json={"username": username, "auth_hash": auth_hash})
            if res.status_code == 200:
                self.current_user = username
                self.symmetric_key = encryption_key
                self.reset_inactivity_timer()
                automatic_cloud_download(username, username)
                self.show_main_screen()
            else:
                self.lbl_error.configure(text="Invalid credentials.", text_color="#ff4a4a")
        except requests.exceptions.ConnectionError:
            self.current_user = username
            self.symmetric_key = encryption_key
            self.reset_inactivity_timer()
            print("\n[OFFLINE MODE] Starting vault in local mode.")
            self.show_main_screen()

    def show_main_screen(self):
        self.clear_screen()
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(8, weight=1)
        
        ctk.CTkLabel(self.sidebar, text="󰌾 Vault", font=self.icon_title_font).grid(row=0, column=0, padx=20, pady=(30, 5), sticky="w")
        ctk.CTkLabel(self.sidebar, text=f" {self.current_user}", font=("Roboto", 12), text_color="gray").grid(row=1, column=0, padx=20, pady=(0, 30), sticky="w")
        
        ctk.CTkButton(self.sidebar, text=" All Accounts", anchor="w", fg_color="transparent", font=self.icon_button_font, command=self.show_list_view).grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        ctk.CTkButton(self.sidebar, text="󰈀 Local Passwords", anchor="w", fg_color="transparent", font=self.icon_button_font, command=self.show_local_view).grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        ctk.CTkButton(self.sidebar, text=" Add Item", anchor="w", fg_color="transparent", font=self.icon_button_font, command=self.show_form_view).grid(row=4, column=0, padx=10, pady=5, sticky="ew")
        ctk.CTkButton(self.sidebar, text=" Settings", anchor="w", fg_color="transparent", font=self.icon_button_font, command=self.show_settings_view).grid(row=5, column=0, padx=10, pady=5, sticky="ew")
        
        ctk.CTkButton(self.sidebar, text=" Lock Vault", anchor="w", fg_color="transparent", font=self.icon_button_font, command=self.lock_vault).grid(row=6, column=0, padx=10, pady=5, sticky="ew")
        ctk.CTkButton(self.sidebar, text=" Exit", fg_color="#3b3b3b", hover_color="#ff4a4a", font=self.icon_button_font, command=self.exit_app).grid(row=7, column=0, padx=20, pady=30, sticky="ew")

        self.central_panel = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.central_panel.grid(row=0, column=1, sticky="nsew", padx=30, pady=30)
        self.central_panel.grid_rowconfigure(1, weight=1)
        self.central_panel.grid_columnconfigure(0, weight=1)
        
        self.show_list_view()

    def clear_central_panel(self):
        for widget in self.central_panel.winfo_children():
            widget.destroy()

    def sync_single_credential(self, db_id):
        if not messagebox.askyesno("Sync Warning", " Once you sync you can't redo this.\n\nAre you sure you want to proceed?"):
            return
            
        try:
            connection = sqlite3.connect("vault_local.db")
            cursor = connection.cursor()
            cursor.execute("SELECT nonce_hex, encrypted_data_hex FROM local_credentials WHERE id = ?", (db_id,))
            row = cursor.fetchone()
            
            if row:
                nonce_hex, encrypted_data_hex = row[0], row[1]
                payload = {"user_id": self.current_user, "nonce_hex": nonce_hex, "encrypted_data_hex": encrypted_data_hex}
                
                response = requests.post(f"{SERVER_URL}/api/sync", json=payload, timeout=5)

                if response.status_code in (200, 201):
                    cursor.execute("UPDATE local_credentials SET estado = 'Cloud' WHERE id = ?", (db_id,))
                    connection.commit()
                    messagebox.showinfo("Sync Status", " Password successfully synced to the cloud!")
                    self.clear_central_panel()
                    self.show_list_view()
                else:
                    messagebox.showerror("Sync Error", f" Server rejected sync: {response.text}")
            connection.close()
        except Exception as e:
            messagebox.showerror("Sync Error", f" Synchronization failed: {e}")

    def show_list_view(self):
        self._show_credentials_view(include_cloud=True, title_text="󰆼 Safe Box")

    def show_local_view(self):
        self._show_credentials_view(include_cloud=False, title_text="󰈀 Local Passwords")

    def _show_credentials_view(self, include_cloud, title_text):
        self.clear_central_panel()
        header = ctk.CTkFrame(self.central_panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        header.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(header, text=title_text, font=self.icon_title_font).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(header, text=" Refresh", width=120, font=self.icon_button_font, command=lambda: self._show_credentials_view(include_cloud, title_text)).grid(row=0, column=1, sticky="e")
        
        self.scroll_frame = ctk.CTkScrollableFrame(self.central_panel, fg_color="transparent")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")
        self.load_and_decrypt_data(include_cloud=include_cloud)

    def load_and_decrypt_data(self, include_cloud=True):
        combined_list = []
        try:
            connection = sqlite3.connect("vault_local.db")
            cursor = connection.cursor()
            cursor.execute("SELECT id, nonce_hex, encrypted_data_hex, estado FROM local_credentials WHERE user_id = ?", (self.current_user,))
            for row in cursor.fetchall():
                estado = row[3] if row[3] else "Local"
                source = " Cloud" if estado == "Cloud" else " Local"
                combined_list.append({"id": row[0], "nonce_hex": row[1], "encrypted_data_hex": row[2], "source": source})
            connection.close()
        except Exception as e:
            print(f"Error loading local data: {e}")

        if not combined_list:
            ctk.CTkLabel(self.scroll_frame, text=" Vault is empty.", text_color="gray", font=self.icon_button_font).pack(pady=40)
            return

        for cred in combined_list:
            nonce = bytes.fromhex(cred["nonce_hex"])
            encrypted_bytes = bytes.fromhex(cred["encrypted_data_hex"])
            if len(encrypted_bytes) < 16: continue
                
            plain_length = len(encrypted_bytes) - 16
            decrypted_buffer = ctypes.create_string_buffer(plain_length + 1)
            
            if self.core.descifrar_credencial(encrypted_bytes, len(encrypted_bytes), nonce, self.symmetric_key, decrypted_buffer) == 0:
                try:
                    data_dict = json.loads(decrypted_buffer.value.decode('utf-8'))
                    self.create_credential_card(cred["id"], data_dict.get("service", ""), data_dict.get("username", ""), data_dict.get("password", ""), cred["source"])
                except Exception:
                    pass

    def create_credential_card(self, db_id, service, username, password, source):
        card = ctk.CTkFrame(self.scroll_frame, corner_radius=10, fg_color="#2b2b2b")
        card.pack(fill="x", pady=8, padx=5)
        
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=20, pady=15)
        
        source_color = "#4aff6b" if "Local" in source else "#5cacee"
        ctk.CTkLabel(info_frame, text=source, font=("Roboto", 10, "bold"), text_color=source_color).pack(anchor="w")
        ctk.CTkLabel(info_frame, text=service, font=("Roboto", 18, "bold")).pack(anchor="w")
        ctk.CTkLabel(info_frame, text=f" {username}", font=("Roboto", 14), text_color="gray").pack(anchor="w", pady=(2,0))
        
        pwd_frame = ctk.CTkFrame(card, fg_color="transparent")
        pwd_frame.pack(side="right", padx=20, pady=15)
        
        entry_pwd = ctk.CTkEntry(pwd_frame, width=180, show="*")
        entry_pwd.insert(0, password)
        entry_pwd.configure(state="readonly")
        entry_pwd.pack(side="left", padx=(0, 10))
        
        def toggle():
            if entry_pwd.cget("show") == "*":
                entry_pwd.configure(show="")
                btn_show.configure(text=" Hide")
            else:
                entry_pwd.configure(show="*")
                btn_show.configure(text=" Show")

        btn_show = ctk.CTkButton(pwd_frame, text=" Show", width=80, fg_color="#3b3b3b", hover_color="#555555", font=self.icon_button_font, command=toggle)
        btn_show.pack(side="left", padx=(0, 5))
        
        def copy_to_clipboard():
            self.clipboard_clear()
            self.clipboard_append(password)
            btn_copy.configure(text=" Copied", text_color="#4aff6b")
            self.after(2000, lambda: btn_copy.configure(text=" Copy", text_color="white"))
            self.after(10000, self.clipboard_clear)
            
        btn_copy = ctk.CTkButton(pwd_frame, text=" Copy", width=80, fg_color="#3b3b3b", hover_color="#555555", font=self.icon_button_font, command=copy_to_clipboard)
        btn_copy.pack(side="left", padx=(0, 5))

        if "Local" in source:
            btn_sync = ctk.CTkButton(pwd_frame, text=" Sync", width=80, fg_color="#3b3b3b", hover_color="#5cacee", font=self.icon_button_font, command=lambda: self.sync_single_credential(db_id))
            btn_sync.pack(side="left", padx=(0, 5))

        def delete_item():
            if not messagebox.askyesno("Confirm", f"Delete '{service}'?"): return
            try:
                if "Cloud" in source:
                    requests.delete(f"{SERVER_URL}/api/sync/{self.current_user}/{db_id}", timeout=3)
                connection = sqlite3.connect("vault_local.db")
                cursor = connection.cursor()
                cursor.execute("DELETE FROM local_credentials WHERE id = ?", (db_id,))
                connection.commit()
                connection.close()
                card.destroy()
            except Exception as e:
                print(f"Delete failed: {e}")

        ctk.CTkButton(pwd_frame, text=" Delete", width=80, fg_color="#3b3b3b", hover_color="#ff4a4a", font=self.icon_button_font, command=delete_item).pack(side="left")

    def show_form_view(self):
        self.clear_central_panel()
        ctk.CTkLabel(self.central_panel, text=" Add Item", font=self.icon_title_font).grid(row=0, column=0, sticky="w", pady=(0, 20))
        
        form_frame = ctk.CTkFrame(self.central_panel, corner_radius=10, fg_color="#2b2b2b")
        form_frame.grid(row=1, column=0, sticky="nsew")
        
        ctk.CTkLabel(form_frame, text="Service Name").pack(anchor="w", padx=30, pady=(20, 5))
        self.entry_service = ctk.CTkEntry(form_frame, width=400, height=40)
        self.entry_service.pack(anchor="w", padx=30)
        
        ctk.CTkLabel(form_frame, text="Username / Email").pack(anchor="w", padx=30, pady=(15, 5))
        self.entry_username = ctk.CTkEntry(form_frame, width=400, height=40)
        self.entry_username.pack(anchor="w", padx=30)
        
        ctk.CTkLabel(form_frame, text="Password").pack(anchor="w", padx=30, pady=(15, 5))
        pwd_container = ctk.CTkFrame(form_frame, fg_color="transparent")
        pwd_container.pack(anchor="w", padx=30)
        
        self.entry_pass = ctk.CTkEntry(pwd_container, width=340, height=40, show="*")
        self.entry_pass.pack(side="left", padx=(0, 10))
        
        btn_gen = ctk.CTkButton(pwd_container, text=" Gen", width=70, height=40, fg_color="#3b3b3b", font=self.icon_button_font, command=self.generate_password)
        btn_gen.pack(side="left")

        # Custom Generator Options
        opt_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        opt_frame.pack(anchor="w", padx=30, pady=(5, 10))
        
        ctk.CTkLabel(opt_frame, text="Length:").pack(side="left")
        lbl_len = ctk.CTkLabel(opt_frame, text=str(self.gen_len.get()), width=20)
        lbl_len.pack(side="left", padx=(5, 10))
        
        def update_len_lbl(val): lbl_len.configure(text=str(int(val)))
        ctk.CTkSlider(opt_frame, from_=8, to=32, variable=self.gen_len, command=update_len_lbl, width=120).pack(side="left", padx=(0, 20))
        
        ctk.CTkCheckBox(opt_frame, text="A-Z", variable=self.gen_upper, width=50).pack(side="left", padx=5)
        ctk.CTkCheckBox(opt_frame, text="0-9", variable=self.gen_nums, width=50).pack(side="left", padx=5)
        ctk.CTkCheckBox(opt_frame, text="!@#", variable=self.gen_syms, width=50).pack(side="left", padx=5)
        
        self.switch_var = ctk.IntVar(value=0)
        ctk.CTkSwitch(form_frame, text=" Sync to Cloud", variable=self.switch_var).pack(anchor="w", padx=30, pady=(15, 10))
        
        ctk.CTkButton(form_frame, text=" Save to Vault", height=45, width=200, command=self.save_data).pack(anchor="w", padx=30, pady=(10, 30))

    def generate_password(self):
        chars = string.ascii_lowercase
        if self.gen_upper.get(): chars += string.ascii_uppercase
        if self.gen_nums.get(): chars += string.digits
        if self.gen_syms.get(): chars += "!@#$%^&*"
        
        if not chars: chars = string.ascii_lowercase
        
        pwd = "".join(secrets.choice(chars) for _ in range(self.gen_len.get()))
        self.entry_pass.delete(0, 'end')
        self.entry_pass.insert(0, pwd)
        self.entry_pass.configure(show="")

    def show_settings_view(self):
        self.clear_central_panel()
        ctk.CTkLabel(self.central_panel, text=" Settings & Security", font=self.icon_title_font).grid(row=0, column=0, sticky="w", pady=(0, 20))
        
        frame = ctk.CTkFrame(self.central_panel, corner_radius=10, fg_color="#2b2b2b")
        frame.grid(row=1, column=0, sticky="nsew")
        
        ctk.CTkLabel(frame, text="Change Master Password", font=("Roboto", 18, "bold")).pack(anchor="w", padx=30, pady=(20, 10))
        
        ctk.CTkLabel(frame, text="Current Password").pack(anchor="w", padx=30, pady=(5, 5))
        self.entry_old_pwd = ctk.CTkEntry(frame, width=300, show="*")
        self.entry_old_pwd.pack(anchor="w", padx=30)
        
        ctk.CTkLabel(frame, text="New Password").pack(anchor="w", padx=30, pady=(15, 5))
        self.entry_new_pwd = ctk.CTkEntry(frame, width=300, show="*")
        self.entry_new_pwd.pack(anchor="w", padx=30)
        
        ctk.CTkButton(frame, text=" Re-Encrypt Vault", fg_color="#ff4a4a", hover_color="#cc0000", height=40, font=self.icon_button_font, command=self.execute_reencryption).pack(anchor="w", padx=30, pady=(25, 30))

    def execute_reencryption(self):
        old_pwd = self.entry_old_pwd.get()
        new_pwd = self.entry_new_pwd.get()
        
        if not old_pwd or not new_pwd:
            messagebox.showwarning("Warning", "Please fill in both password fields.")
            return
            
        old_hash, old_key = self.process_keys(old_pwd)
        
        if old_key != self.symmetric_key:
            messagebox.showerror("Security Error", "Current master password is incorrect.")
            return
            
        if not messagebox.askyesno("Critical Action", "This will decrypt and re-encrypt your entire vault with the new password.\n\nDo not close the application during this process. Proceed?"):
            return
            
        new_hash, new_key = self.process_keys(new_pwd)
        
        try:
            conn = sqlite3.connect("vault_local.db")
            cursor = conn.cursor()
            cursor.execute("SELECT id, nonce_hex, encrypted_data_hex FROM local_credentials WHERE user_id = ?", (self.current_user,))
            rows = cursor.fetchall()
            
            for row in rows:
                db_id, nonce_hex, enc_hex = row
                nonce = bytes.fromhex(nonce_hex)
                enc_bytes = bytes.fromhex(enc_hex)
                
                plain_len = len(enc_bytes) - 16
                dec_buf = ctypes.create_string_buffer(plain_len + 1)
                if self.core.descifrar_credencial(enc_bytes, len(enc_bytes), nonce, old_key, dec_buf) != 0:
                    continue 
                    
                new_nonce = secrets.token_bytes(24)
                enc_buf = ctypes.create_string_buffer(plain_len + 16)
                self.core.cifrar_credencial(dec_buf.raw[:plain_len], plain_len, new_nonce, new_key, enc_buf)
                
                cursor.execute("UPDATE local_credentials SET nonce_hex = ?, encrypted_data_hex = ?, estado = 'Local' WHERE id = ?", (new_nonce.hex(), enc_buf.raw.hex(), db_id))
                
            conn.commit()
            conn.close()

            # Enviar el nuevo hash a Render
            try:
                res = requests.put(f"{SERVER_URL}/api/update_hash", json={
                    "username": self.current_user,
                    "old_auth_hash": old_hash,
                    "new_auth_hash": new_hash
                }, timeout=5)
                
                if res.status_code != 200:
                    messagebox.showwarning("Cloud Warning", "Local vault re-encrypted, but failed to sync new master password to the cloud. You might need to login offline.")
            except requests.exceptions.ConnectionError:
                messagebox.showwarning("Offline", "Vault re-encrypted locally, but you are offline. Cloud password not updated.")

            self.symmetric_key = new_key
            messagebox.showinfo("Success", "Vault re-encrypted successfully!\n\nAll items have been marked as 'Local'. Please use the Sync buttons to update the cloud with your new encryption keys.")
            self.entry_old_pwd.delete(0, 'end')
            self.entry_new_pwd.delete(0, 'end')
            self.show_list_view()
            
        except Exception as e:
            messagebox.showerror("Fatal Error", f"Failed to re-encrypt: {e}")

    def save_data(self):
        service, username, password = self.entry_service.get(), self.entry_username.get(), self.entry_pass.get()
        if not service or not username or not password: return
            
        data = json.dumps({"service": service, "username": username, "password": password}).encode('utf-8')
        length = len(data)
        nonce = secrets.token_bytes(24) 
        buffer = ctypes.create_string_buffer(length + 16)
        
        if self.core.cifrar_credencial(data, length, nonce, self.symmetric_key, buffer) != 0: return

        estado = "Cloud" if self.switch_var.get() == 1 else "Local"
        
        connection = sqlite3.connect("vault_local.db")
        cursor = connection.cursor()
        cursor.execute("INSERT INTO local_credentials (user_id, nonce_hex, encrypted_data_hex, estado) VALUES (?, ?, ?, ?)",(self.current_user, nonce.hex(), buffer.raw.hex(), estado))
        connection.commit()
        connection.close()

        if estado == "Cloud":
            try:
                requests.post(f"{SERVER_URL}/api/sync", json={"user_id": self.current_user, "nonce_hex": nonce.hex(), "encrypted_data_hex": buffer.raw.hex()}, timeout=3)
            except Exception:
                pass
                
        self.show_list_view()

    def exit_app(self):
        self.destroy()

if __name__ == "__main__":
    app = VaultApp()
    app.mainloop()