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

# Server URL for the backend API
SERVER_URL = "http://127.0.0.1:8000"

def load_crypto_core():
    # Load the C cryptographic library (libvault_crypto.so) using ctypes
    current_path = os.path.dirname(os.path.abspath(__file__))
    lib_path = os.path.join(current_path, "../core_crypto/libvault_crypto.so")
    core_lib = ctypes.CDLL(lib_path)
    
    # Configure C function prototypes and argument types for type safety
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
        self.geometry("950x600")
        self.minsize(850, 500)
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.core = load_crypto_core()
        if self.core.inicializar_motor() < 0:
            print("Fatal error with libsodium.")
            self.destroy()
            
        self.symmetric_key = None
        self.current_user = None
        
        self.initialize_local_db()
        self.show_welcome_screen()

    def initialize_local_db(self):
        # Initialize local SQLite database for offline credential storage
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
        connection.commit()
        connection.close()

    def clear_screen(self):
        # Remove all child widgets from window for screen transition
        for widget in self.winfo_children():
            widget.destroy()

    def process_keys(self, password):
        # Derive authentication hash and symmetric encryption key from master password
        auth_hash = hashlib.sha256((password + "auth_salt").encode('utf-8')).hexdigest()
        encryption_key = hashlib.sha256((password + "enc_salt").encode('utf-8')).digest()
        return auth_hash, encryption_key

    def show_welcome_screen(self):
        self.clear_screen()
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        login_frame = ctk.CTkFrame(self, fg_color="transparent")
        login_frame.grid(row=0, column=0)
        
        ctk.CTkLabel(login_frame, text="", font=("Roboto", 60)).pack(pady=(0, 10))
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
                self.show_main_screen()
            else:
                self.lbl_error.configure(text="Invalid credentials.", text_color="#ff4a4a")
        except requests.exceptions.ConnectionError:
            self.current_user = username
            self.symmetric_key = encryption_key
            print("\n[OFFLINE MODE] Starting vault in local mode without cloud synchronization.")
            self.show_main_screen()

    def show_main_screen(self):
        self.clear_screen()
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1)
        
        ctk.CTkLabel(self.sidebar, text=" Vault", font=("Roboto", 24, "bold")).grid(row=0, column=0, padx=20, pady=(30, 5), sticky="w")
        ctk.CTkLabel(self.sidebar, text=f" {self.current_user}", font=("Roboto", 12), text_color="gray").grid(row=1, column=0, padx=20, pady=(0, 30), sticky="w")
        
        ctk.CTkButton(self.sidebar, text=" All Accounts", anchor="w", fg_color="transparent", command=self.show_list_view).grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        ctk.CTkButton(self.sidebar, text=" Add Item", anchor="w", fg_color="transparent", command=self.show_form_view).grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        ctk.CTkButton(self.sidebar, text=" Logout", fg_color="#3b3b3b", hover_color="#ff4a4a", command=self.show_welcome_screen).grid(row=5, column=0, padx=20, pady=30, sticky="ew")

        self.central_panel = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.central_panel.grid(row=0, column=1, sticky="nsew", padx=30, pady=30)
        self.central_panel.grid_rowconfigure(1, weight=1)
        self.central_panel.grid_columnconfigure(0, weight=1)
        
        self.show_list_view()

    def clear_central_panel(self):
        # Clear central display panel of all child widgets
        for widget in self.central_panel.winfo_children():
            widget.destroy()

    def show_list_view(self):
        self.clear_central_panel()
        header = ctk.CTkFrame(self.central_panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        header.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(header, text="Safe Box", font=("Roboto", 28, "bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(header, text=" Refresh", width=120, command=self.show_list_view).grid(row=0, column=1, sticky="e")
        
        self.scroll_frame = ctk.CTkScrollableFrame(self.central_panel, fg_color="transparent")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")
        self.load_and_decrypt_data()

    def load_and_decrypt_data(self):
        combined_list = []

        # Load local data
        try:
            connection = sqlite3.connect("vault_local.db")
            cursor = connection.cursor()
            cursor.execute("SELECT id, nonce_hex, encrypted_data_hex FROM local_credentials WHERE user_id = ?", (self.current_user,))
            rows = cursor.fetchall()
            for row in rows:
                combined_list.append({"id": row[0], "nonce_hex": row[1], "encrypted_data_hex": row[2], "source": " Local"})
            connection.close()
        except Exception:
            pass

        # Fetch and load cloud data
        try:
            response = requests.get(f"{SERVER_URL}/api/sync/{self.current_user}", timeout=2)
            if response.status_code == 200:
                cloud_data = response.json().get("credentials", [])
                for cred in cloud_data:
                    combined_list.append({"id": cred["id"], "nonce_hex": cred["nonce_hex"], "encrypted_data_hex": cred["encrypted_data_hex"], "source": " Cloud"})
        except requests.exceptions.ConnectionError:
            ctk.CTkLabel(self.scroll_frame, text=" Offline Mode: Displaying local credentials only", text_color="#ffcc00").pack(pady=(0,10))

        if not combined_list:
            ctk.CTkLabel(self.scroll_frame, text="Vault is empty.", text_color="gray").pack(pady=40)
            return

        for cred in combined_list:
            nonce = bytes.fromhex(cred["nonce_hex"])
            encrypted_bytes = bytes.fromhex(cred["encrypted_data_hex"])
            
            if len(encrypted_bytes) < 16:
                continue
                
            plain_length = len(encrypted_bytes) - 16
            decrypted_buffer = ctypes.create_string_buffer(plain_length + 1)
            
            if self.core.descifrar_credencial(encrypted_bytes, len(encrypted_bytes), nonce, self.symmetric_key, decrypted_buffer) == 0:
                text = decrypted_buffer.value.decode('utf-8')
                try:
                    data_dict = json.loads(text)
                    self.create_credential_card(cred["id"], data_dict.get("service", ""), data_dict.get("username", ""), data_dict.get("password", ""), cred["source"])
                except json.JSONDecodeError:
                    pass
            else:
                ctk.CTkLabel(self.scroll_frame, text=" Decryption Error", text_color="#ff4a4a").pack(pady=10)

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
                btn_show.configure(text=" Hide")
            else:
                entry_pwd.configure(show="*")
                btn_show.configure(text=" Show")
                
        btn_show = ctk.CTkButton(pwd_frame, text=" Show", width=80, fg_color="#3b3b3b", hover_color="#555555", command=toggle)
        btn_show.pack(side="left", padx=(0, 5))
        
        def copy_to_clipboard():
            self.clipboard_clear()
            self.clipboard_append(password)
            btn_copy.configure(text=" Copied", text_color="#4aff6b")
            self.after(2000, lambda: btn_copy.configure(text=" Copy", text_color="white"))
            
        btn_copy = ctk.CTkButton(pwd_frame, text=" Copy", width=80, fg_color="#3b3b3b", hover_color="#555555", command=copy_to_clipboard)
        btn_copy.pack(side="left", padx=(0, 5))

        # Edit button for modifying existing credentials
        btn_edit = ctk.CTkButton(pwd_frame, text=" Edit", width=80, fg_color="#3b3b3b", hover_color="#ffcc00", command=lambda: self.prepare_edit_view(db_id, service, username, password, source))
        btn_edit.pack(side="left", padx=(0, 5))

        def delete_item():
            # Request user confirmation before permanent deletion
            confirmation = messagebox.askyesno(
                title="Confirm Deletion",
                message=f"Are you sure you want to delete '{service}'?\n\nThis action cannot be undone."
            )
            if not confirmation:
                return

            if "Local" in source:
                try:
                    connection = sqlite3.connect("vault_local.db")
                    cursor = connection.cursor()
                    cursor.execute("DELETE FROM local_credentials WHERE id = ?", (db_id,))
                    connection.commit()
                    connection.close()
                    card.destroy()
                except Exception as e:
                    print(f"Error deleting: {e}")
            else:
                try:
                    res = requests.delete(f"{SERVER_URL}/api/sync/{self.current_user}/{db_id}", timeout=3)
                    if res.status_code == 200:
                        card.destroy()
                except Exception as e:
                    print(f"Error deleting from cloud: {e}")

        btn_delete = ctk.CTkButton(pwd_frame, text=" Delete", width=80, fg_color="#3b3b3b", hover_color="#ff4a4a", command=delete_item)
        btn_delete.pack(side="left")

    # ==========================================
    # CREDENTIAL FORM MANAGEMENT: CREATE, EDIT, DELETE
    # ==========================================
    def show_form_view(self):
        self.clear_central_panel()
        ctk.CTkLabel(self.central_panel, text="Add Item", font=("Roboto", 28, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 20))
        
        form_frame = ctk.CTkFrame(self.central_panel, corner_radius=10, fg_color="#2b2b2b")
        form_frame.grid(row=1, column=0, sticky="nsew")
        
        ctk.CTkLabel(form_frame, text="Service Name", font=("Roboto", 14)).pack(anchor="w", padx=30, pady=(20, 5))
        self.entry_service = ctk.CTkEntry(form_frame, width=400, height=40)
        self.entry_service.pack(anchor="w", padx=30)
        
        ctk.CTkLabel(form_frame, text="Username / Email", font=("Roboto", 14)).pack(anchor="w", padx=30, pady=(15, 5))
        self.entry_username = ctk.CTkEntry(form_frame, width=400, height=40)
        self.entry_username.pack(anchor="w", padx=30)
        
        ctk.CTkLabel(form_frame, text="Password", font=("Roboto", 14)).pack(anchor="w", padx=30, pady=(15, 5))
        
        pwd_container = ctk.CTkFrame(form_frame, fg_color="transparent")
        pwd_container.pack(anchor="w", padx=30)
        
        self.entry_pass = ctk.CTkEntry(pwd_container, width=340, height=40, show="*")
        self.entry_pass.pack(side="left", padx=(0, 10))
        
        btn_gen = ctk.CTkButton(pwd_container, text=" Gen", width=70, height=40, fg_color="#3b3b3b", hover_color="#555555", command=self.generate_password)
        btn_gen.pack(side="left")
        
        self.switch_var = ctk.IntVar(value=0)
        self.switch_cloud = ctk.CTkSwitch(form_frame, text=" Sync to Cloud (Off = Local Save)", variable=self.switch_var, font=("Roboto", 13))
        self.switch_cloud.pack(anchor="w", padx=30, pady=(20, 10))
        
        self.lbl_status = ctk.CTkLabel(form_frame, text="", font=("Roboto", 14))
        self.lbl_status.pack(anchor="w", padx=30, pady=5)
        
        ctk.CTkButton(form_frame, text="Save to Vault", height=45, width=200, command=self.save_data).pack(anchor="w", padx=30, pady=(0, 30))

    def prepare_edit_view(self, db_id, service, username, password, source):
        self.clear_central_panel()
        ctk.CTkLabel(self.central_panel, text="Edit Item", font=("Roboto", 28, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 20))

        form_frame = ctk.CTkFrame(self.central_panel, corner_radius=10, fg_color="#2b2b2b")
        form_frame.grid(row=1, column=0, sticky="nsew")

        ctk.CTkLabel(form_frame, text="Service Name", font=("Roboto", 14)).pack(anchor="w", padx=30, pady=(20, 5))
        self.entry_service = ctk.CTkEntry(form_frame, width=400, height=40)
        self.entry_service.insert(0, service)
        self.entry_service.pack(anchor="w", padx=30)

        ctk.CTkLabel(form_frame, text="Username / Email", font=("Roboto", 14)).pack(anchor="w", padx=30, pady=(15, 5))
        self.entry_username = ctk.CTkEntry(form_frame, width=400, height=40)
        self.entry_username.insert(0, username)
        self.entry_username.pack(anchor="w", padx=30)

        ctk.CTkLabel(form_frame, text="Password", font=("Roboto", 14)).pack(anchor="w", padx=30, pady=(15, 5))

        pwd_container = ctk.CTkFrame(form_frame, fg_color="transparent")
        pwd_container.pack(anchor="w", padx=30)

        self.entry_pass = ctk.CTkEntry(pwd_container, width=340, height=40, show="*")
        self.entry_pass.insert(0, password)
        self.entry_pass.pack(side="left", padx=(0, 10))

        btn_gen = ctk.CTkButton(pwd_container, text=" Gen", width=70, height=40, fg_color="#3b3b3b", hover_color="#555555", command=self.generate_password)
        btn_gen.pack(side="left")

        # Prevent storage location change during edit to maintain data consistency
        ctk.CTkLabel(form_frame, text=f" Storage: {source} (immutable during edit)", font=("Roboto", 12), text_color="gray").pack(anchor="w", padx=30, pady=(20, 0))

        self.lbl_status = ctk.CTkLabel(form_frame, text="", font=("Roboto", 14))
        self.lbl_status.pack(anchor="w", padx=30, pady=5)

        buttons_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        buttons_frame.pack(anchor="w", padx=30, pady=(0, 30))

        ctk.CTkButton(buttons_frame, text=" Save Changes", height=45, width=170, command=lambda: self.update_data(db_id, source)).pack(side="left", padx=(0, 10))
        ctk.CTkButton(buttons_frame, text=" Cancel", height=45, width=100, fg_color="#3b3b3b", hover_color="#555555", command=self.show_list_view).pack(side="left")

    def generate_password(self):
        # Generate cryptographically secure 16-character password with mixed character types
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        secure_pwd = "".join(secrets.choice(characters) for _ in range(16))
        self.entry_pass.delete(0, 'end')
        self.entry_pass.insert(0, secure_pwd)
        self.entry_pass.configure(show="")  # Display password for user verification

    def save_data(self):
        service = self.entry_service.get()
        username = self.entry_username.get()
        password = self.entry_pass.get()
        
        if not service or not username or not password:
            self.lbl_status.configure(text="Please fill all fields.", text_color="#ff4a4a")
            return
            
        data = json.dumps({"service": service, "username": username, "password": password}).encode('utf-8')
        length = len(data)
        nonce = secrets.token_bytes(24) 
        buffer = ctypes.create_string_buffer(length + 16)
        
        if self.core.cifrar_credencial(data, length, nonce, self.symmetric_key, buffer) != 0:
            self.lbl_status.configure(text="Encryption error.", text_color="#ff4a4a")
            return

        if self.switch_var.get() == 0:
            # Save locally
            try:
                connection = sqlite3.connect("vault_local.db")
                cursor = connection.cursor()
                cursor.execute("INSERT INTO local_credentials (user_id, nonce_hex, encrypted_data_hex) VALUES (?, ?, ?)",(self.current_user, nonce.hex(), buffer.raw.hex()))
                connection.commit()
                connection.close()
                self.lbl_status.configure(text=" Saved Locally", text_color="#4aff6b")
                self.after(1000, self.show_list_view)
            except Exception as e:
                self.lbl_status.configure(text="Error saving to disk.", text_color="#ff4a4a")
        else:
            # Sync with cloud
            try:
                res = requests.post(f"{SERVER_URL}/api/sync", json={"user_id": self.current_user, "nonce_hex": nonce.hex(), "encrypted_data_hex": buffer.raw.hex()}, timeout=3)
                if res.status_code == 200:
                    self.lbl_status.configure(text=" Synced to Cloud", text_color="#5cacee")
                    self.after(1000, self.show_list_view)
            except requests.exceptions.ConnectionError:
                self.lbl_status.configure(text="Network error.", text_color="#ff4a4a")

    def update_data(self, db_id, source):
        service = self.entry_service.get()
        username = self.entry_username.get()
        password = self.entry_pass.get()
        
        if not service or not username or not password:
            self.lbl_status.configure(text="Please fill all fields.", text_color="#ff4a4a")
            return
            
        data = json.dumps({"service": service, "username": username, "password": password}).encode('utf-8')
        length = len(data)
        nonce = secrets.token_bytes(24) 
        buffer = ctypes.create_string_buffer(length + 16)
        
        if self.core.cifrar_credencial(data, length, nonce, self.symmetric_key, buffer) != 0:
            self.lbl_status.configure(text="Encryption error.", text_color="#ff4a4a")
            return

        if "Local" in source:
            try:
                connection = sqlite3.connect("vault_local.db")
                cursor = connection.cursor()
                cursor.execute("UPDATE local_credentials SET nonce_hex = ?, encrypted_data_hex = ? WHERE id = ?", (nonce.hex(), buffer.raw.hex(), db_id))
                connection.commit()
                connection.close()
                self.lbl_status.configure(text=" Updated Locally", text_color="#4aff6b")
                self.after(1000, self.show_list_view)
            except Exception as e:
                self.lbl_status.configure(text="Error updating.", text_color="#ff4a4a")
        else:
            try:
                res = requests.put(f"{SERVER_URL}/api/sync/{self.current_user}/{db_id}", json={"nonce_hex": nonce.hex(), "encrypted_data_hex": buffer.raw.hex()}, timeout=3)
                if res.status_code == 200:
                    self.lbl_status.configure(text=" Updated in Cloud", text_color="#5cacee")
                    self.after(1000, self.show_list_view)
            except requests.exceptions.ConnectionError:
                self.lbl_status.configure(text="Network error.", text_color="#ff4a4a")

if __name__ == "__main__":
    app = VaultApp()
    app.mainloop()