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

URL_SERVIDOR = "http://127.0.0.1:8000"

def cargar_core_criptografico():
    ruta_actual = os.path.dirname(os.path.abspath(__file__))
    ruta_lib = os.path.join(ruta_actual, "../core_crypto/libvault_crypto.so")
    core_lib = ctypes.CDLL(ruta_lib)
    
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
        
        self.core = cargar_core_criptografico()
        if self.core.inicializar_motor() < 0:
            print("Error fatal con libsodium.")
            self.destroy()
            
        self.clave_simetrica = None
        self.usuario_actual = None
        
        self.inicializar_db_local()
        self.pantalla_bienvenida()

    def inicializar_db_local(self):
        conexion = sqlite3.connect("boveda_local.db")
        cursor = conexion.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS credenciales_locales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_usuario TEXT,
                nonce_hex TEXT,
                datos_cifrados_hex TEXT
            )
        ''')
        conexion.commit()
        conexion.close()

    def limpiar_pantalla(self):
        for widget in self.winfo_children():
            widget.destroy()

    def procesar_claves(self, password):
        auth_hash = hashlib.sha256((password + "auth_salt").encode('utf-8')).hexdigest()
        clave_cifrado = hashlib.sha256((password + "enc_salt").encode('utf-8')).digest()
        return auth_hash, clave_cifrado

    def pantalla_bienvenida(self):
        self.limpiar_pantalla()
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        frame_login = ctk.CTkFrame(self, fg_color="transparent")
        frame_login.grid(row=0, column=0)
        
        ctk.CTkLabel(frame_login, text="🛡️", font=("Roboto", 60)).pack(pady=(0, 10))
        ctk.CTkLabel(frame_login, text="Vault Authentication", font=("Roboto", 24, "bold")).pack(pady=(0, 30))
        
        self.entry_user = ctk.CTkEntry(frame_login, placeholder_text="Usuario", width=350, height=45)
        self.entry_user.pack(pady=(0, 15))
        
        self.entry_pwd = ctk.CTkEntry(frame_login, placeholder_text="Contraseña Maestra", show="•", width=350, height=45)
        self.entry_pwd.pack(pady=(0, 20))
        
        self.lbl_error = ctk.CTkLabel(frame_login, text="", text_color="#ff4a4a")
        self.lbl_error.pack(pady=(0, 10))
        
        frame_botones = ctk.CTkFrame(frame_login, fg_color="transparent")
        frame_botones.pack()
        
        ctk.CTkButton(frame_botones, text="Iniciar Sesión", command=self.login, width=170, height=40, font=("Roboto", 14, "bold")).pack(side="left", padx=5)
        ctk.CTkButton(frame_botones, text="Crear Cuenta", command=self.register, width=170, height=40, fg_color="#3b3b3b", hover_color="#555555").pack(side="left", padx=5)

    def register(self):
        usuario = self.entry_user.get()
        pwd = self.entry_pwd.get()
        if not usuario or not pwd:
            self.lbl_error.configure(text="Rellena ambos campos.", text_color="#ff4a4a")
            return
        auth_hash, _ = self.procesar_claves(pwd)
        try:
            res = requests.post(f"{URL_SERVIDOR}/api/register", json={"username": usuario, "auth_hash": auth_hash})
            if res.status_code == 200:
                self.lbl_error.configure(text="¡Cuenta creada! Inicia Sesión.", text_color="#4aff6b")
            else:
                self.lbl_error.configure(text="Ese usuario ya existe.", text_color="#ff4a4a")
        except requests.exceptions.ConnectionError:
            self.lbl_error.configure(text="Error de red.", text_color="#ff4a4a")

    def login(self):
        usuario = self.entry_user.get()
        pwd = self.entry_pwd.get()
        if not usuario or not pwd:
            self.lbl_error.configure(text="Rellena ambos campos.", text_color="#ff4a4a")
            return
        
        auth_hash, clave_cifrado = self.procesar_claves(pwd)
        
        try:
            res = requests.post(f"{URL_SERVIDOR}/api/login", json={"username": usuario, "auth_hash": auth_hash})
            if res.status_code == 200:
                self.usuario_actual = usuario
                self.clave_simetrica = clave_cifrado
                self.pantalla_principal()
            else:
                self.lbl_error.configure(text="Credenciales incorrectas.", text_color="#ff4a4a")
        except requests.exceptions.ConnectionError:
            self.usuario_actual = usuario
            self.clave_simetrica = clave_cifrado
            print("\n[🔌 MODO OFFLINE] Iniciando bóveda en modo local.")
            self.pantalla_principal()

    def pantalla_principal(self):
        self.limpiar_pantalla()
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1)
        
        ctk.CTkLabel(self.sidebar, text="🛡️ Vault", font=("Roboto", 24, "bold")).grid(row=0, column=0, padx=20, pady=(30, 5), sticky="w")
        ctk.CTkLabel(self.sidebar, text=f"👤 {self.usuario_actual}", font=("Roboto", 12), text_color="gray").grid(row=1, column=0, padx=20, pady=(0, 30), sticky="w")
        
        ctk.CTkButton(self.sidebar, text="📋 Todas las cuentas", anchor="w", fg_color="transparent", command=self.mostrar_lista).grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        ctk.CTkButton(self.sidebar, text="➕ Añadir elemento", anchor="w", fg_color="transparent", command=self.mostrar_formulario).grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        ctk.CTkButton(self.sidebar, text="🔒 Cerrar Sesión", fg_color="#3b3b3b", hover_color="#ff4a4a", command=self.pantalla_bienvenida).grid(row=5, column=0, padx=20, pady=30, sticky="ew")

        self.panel_central = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.panel_central.grid(row=0, column=1, sticky="nsew", padx=30, pady=30)
        self.panel_central.grid_rowconfigure(1, weight=1)
        self.panel_central.grid_columnconfigure(0, weight=1)
        
        self.mostrar_lista()

    def limpiar_panel_central(self):
        for widget in self.panel_central.winfo_children():
            widget.destroy()

    def mostrar_lista(self):
        self.limpiar_panel_central()
        header = ctk.CTkFrame(self.panel_central, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        header.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(header, text="Caja Fuerte", font=("Roboto", 28, "bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(header, text="🔄 Sincronizar", width=120, command=self.mostrar_lista).grid(row=0, column=1, sticky="e")
        
        self.scroll_frame = ctk.CTkScrollableFrame(self.panel_central, fg_color="transparent")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")
        self.cargar_y_descifrar_datos()

    def cargar_y_descifrar_datos(self):
        lista_combinada = []

        try:
            conexion = sqlite3.connect("boveda_local.db")
            cursor = conexion.cursor()
            cursor.execute("SELECT id, nonce_hex, datos_cifrados_hex FROM credenciales_locales WHERE id_usuario = ?", (self.usuario_actual,))
            filas = cursor.fetchall()
            for fila in filas:
                lista_combinada.append({"id": fila[0], "nonce_hex": fila[1], "datos_cifrados_hex": fila[2], "origen": "🏠 Local"})
            conexion.close()
        except Exception:
            pass

        try:
            respuesta = requests.get(f"{URL_SERVIDOR}/api/sync/{self.usuario_actual}", timeout=2)
            if respuesta.status_code == 200:
                datos_nube = respuesta.json().get("credenciales", [])
                for cred in datos_nube:
                    lista_combinada.append({"id": cred["id"], "nonce_hex": cred["nonce_hex"], "datos_cifrados_hex": cred["datos_cifrados_hex"], "origen": "☁️ Nube"})
        except requests.exceptions.ConnectionError:
            ctk.CTkLabel(self.scroll_frame, text="Modo Offline: Mostrando solo datos locales.", text_color="#ffcc00").pack(pady=(0,10))

        if not lista_combinada:
            ctk.CTkLabel(self.scroll_frame, text="Bóveda vacía.", text_color="gray").pack(pady=40)
            return

        for cred in lista_combinada:
            nonce = bytes.fromhex(cred["nonce_hex"])
            cifrado_bytes = bytes.fromhex(cred["datos_cifrados_hex"])
            
            if len(cifrado_bytes) < 16:
                continue
                
            longitud_plano = len(cifrado_bytes) - 16
            buffer_descifrado = ctypes.create_string_buffer(longitud_plano + 1)
            
            if self.core.descifrar_credencial(cifrado_bytes, len(cifrado_bytes), nonce, self.clave_simetrica, buffer_descifrado) == 0:
                texto = buffer_descifrado.value.decode('utf-8')
                try:
                    dic = json.loads(texto)
                    self.crear_tarjeta_credencial(cred["id"], dic.get("servicio", ""), dic.get("usuario", ""), dic.get("password", ""), cred["origen"])
                except json.JSONDecodeError:
                    pass
            else:
                ctk.CTkLabel(self.scroll_frame, text="🔒 Error de descifrado", text_color="#ff4a4a").pack(pady=10)

    def crear_tarjeta_credencial(self, db_id, servicio, usuario, password, origen):
        card = ctk.CTkFrame(self.scroll_frame, corner_radius=10, fg_color="#2b2b2b")
        card.pack(fill="x", pady=8, padx=5)
        
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=20, pady=15)
        
        color_origen = "#4aff6b" if "Local" in origen else "#5cacee"
        ctk.CTkLabel(info_frame, text=origen, font=("Roboto", 10, "bold"), text_color=color_origen).pack(anchor="w")
        
        ctk.CTkLabel(info_frame, text=servicio, font=("Roboto", 18, "bold")).pack(anchor="w")
        ctk.CTkLabel(info_frame, text=f"👤 {usuario}", font=("Roboto", 14), text_color="gray").pack(anchor="w", pady=(2,0))
        
        pwd_frame = ctk.CTkFrame(card, fg_color="transparent")
        pwd_frame.pack(side="right", padx=20, pady=15)
        
        entry_pwd = ctk.CTkEntry(pwd_frame, width=180, show="*")
        entry_pwd.insert(0, password)
        entry_pwd.configure(state="readonly")
        entry_pwd.pack(side="left", padx=(0, 10))
        
        def toggle():
            if entry_pwd.cget("show") == "*":
                entry_pwd.configure(show="")
                btn_show.configure(text="🙈")
            else:
                entry_pwd.configure(show="*")
                btn_show.configure(text="👁️")
                
        btn_show = ctk.CTkButton(pwd_frame, text="👁️", width=40, fg_color="#3b3b3b", hover_color="#555555", command=toggle)
        btn_show.pack(side="left", padx=(0, 5))
        
        def copiar():
            self.clipboard_clear()
            self.clipboard_append(password)
            btn_copy.configure(text="✅", text_color="#4aff6b")
            self.after(2000, lambda: btn_copy.configure(text="📋", text_color="white"))
            
        btn_copy = ctk.CTkButton(pwd_frame, text="📋", width=40, fg_color="#3b3b3b", hover_color="#555555", command=copiar)
        btn_copy.pack(side="left", padx=(0, 5))

        # BOTÓN NUEVO: EDITAR ✏️
        btn_editar = ctk.CTkButton(pwd_frame, text="✏️", width=40, fg_color="#3b3b3b", hover_color="#ffcc00", command=lambda: self.preparar_edicion(db_id, servicio, usuario, password, origen))
        btn_editar.pack(side="left", padx=(0, 5))

        def eliminar_elemento():
            confirmacion = messagebox.askyesno(
                title="Confirmar eliminación",
                message=f"¿Estás seguro de que deseas eliminar '{servicio}'?\n\nEsta acción no se puede deshacer."
            )
            if not confirmacion:
                return 

            if "Local" in origen:
                try:
                    conexion = sqlite3.connect("boveda_local.db")
                    cursor = conexion.cursor()
                    cursor.execute("DELETE FROM credenciales_locales WHERE id = ?", (db_id,))
                    conexion.commit()
                    conexion.close()
                    card.destroy()
                except Exception as e:
                    print(f"Error borrando: {e}")
            else:
                try:
                    res = requests.delete(f"{URL_SERVIDOR}/api/sync/{self.usuario_actual}/{db_id}", timeout=3)
                    if res.status_code == 200:
                        card.destroy()
                except Exception as e:
                    print(f"Error borrando en la nube: {e}")

        btn_eliminar = ctk.CTkButton(pwd_frame, text="🗑️", width=40, fg_color="#3b3b3b", hover_color="#ff4a4a", command=eliminar_elemento)
        btn_eliminar.pack(side="left")

    # ==========================================
    # VISTAS DE FORMULARIO (AÑADIR / EDITAR)
    # ==========================================
    def mostrar_formulario(self):
        self.limpiar_panel_central()
        ctk.CTkLabel(self.panel_central, text="Añadir Elemento", font=("Roboto", 28, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 20))
        
        form_frame = ctk.CTkFrame(self.panel_central, corner_radius=10, fg_color="#2b2b2b")
        form_frame.grid(row=1, column=0, sticky="nsew")
        
        ctk.CTkLabel(form_frame, text="Nombre del Servicio", font=("Roboto", 14)).pack(anchor="w", padx=30, pady=(20, 5))
        self.entry_servicio = ctk.CTkEntry(form_frame, width=400, height=40)
        self.entry_servicio.pack(anchor="w", padx=30)
        
        ctk.CTkLabel(form_frame, text="Nombre de Usuario / Correo", font=("Roboto", 14)).pack(anchor="w", padx=30, pady=(15, 5))
        self.entry_usuario = ctk.CTkEntry(form_frame, width=400, height=40)
        self.entry_usuario.pack(anchor="w", padx=30)
        
        ctk.CTkLabel(form_frame, text="Contraseña", font=("Roboto", 14)).pack(anchor="w", padx=30, pady=(15, 5))
        
        pwd_container = ctk.CTkFrame(form_frame, fg_color="transparent")
        pwd_container.pack(anchor="w", padx=30)
        
        self.entry_pass = ctk.CTkEntry(pwd_container, width=340, height=40, show="*")
        self.entry_pass.pack(side="left", padx=(0, 10))
        
        btn_gen = ctk.CTkButton(pwd_container, text="🎲", width=50, height=40, fg_color="#3b3b3b", hover_color="#555555", command=self.generar_password)
        btn_gen.pack(side="left")
        
        self.switch_var = ctk.IntVar(value=0)
        self.switch_nube = ctk.CTkSwitch(form_frame, text="☁️ Sincronizar en la Nube (Desactivado = Guardado Local)", variable=self.switch_var, font=("Roboto", 13))
        self.switch_nube.pack(anchor="w", padx=30, pady=(20, 10))
        
        self.lbl_estado = ctk.CTkLabel(form_frame, text="", font=("Roboto", 14))
        self.lbl_estado.pack(anchor="w", padx=30, pady=5)
        
        ctk.CTkButton(form_frame, text="Guardar en la Bóveda", height=45, width=200, command=self.guardar_datos).pack(anchor="w", padx=30, pady=(0, 30))

    def preparar_edicion(self, db_id, servicio, usuario, password, origen):
        self.limpiar_panel_central()
        ctk.CTkLabel(self.panel_central, text="Editar Elemento", font=("Roboto", 28, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 20))

        form_frame = ctk.CTkFrame(self.panel_central, corner_radius=10, fg_color="#2b2b2b")
        form_frame.grid(row=1, column=0, sticky="nsew")

        ctk.CTkLabel(form_frame, text="Nombre del Servicio", font=("Roboto", 14)).pack(anchor="w", padx=30, pady=(20, 5))
        self.entry_servicio = ctk.CTkEntry(form_frame, width=400, height=40)
        self.entry_servicio.insert(0, servicio)
        self.entry_servicio.pack(anchor="w", padx=30)

        ctk.CTkLabel(form_frame, text="Nombre de Usuario / Correo", font=("Roboto", 14)).pack(anchor="w", padx=30, pady=(15, 5))
        self.entry_usuario = ctk.CTkEntry(form_frame, width=400, height=40)
        self.entry_usuario.insert(0, usuario)
        self.entry_usuario.pack(anchor="w", padx=30)

        ctk.CTkLabel(form_frame, text="Contraseña", font=("Roboto", 14)).pack(anchor="w", padx=30, pady=(15, 5))

        pwd_container = ctk.CTkFrame(form_frame, fg_color="transparent")
        pwd_container.pack(anchor="w", padx=30)

        self.entry_pass = ctk.CTkEntry(pwd_container, width=340, height=40, show="*")
        self.entry_pass.insert(0, password)
        self.entry_pass.pack(side="left", padx=(0, 10))

        btn_gen = ctk.CTkButton(pwd_container, text="🎲", width=50, height=40, fg_color="#3b3b3b", hover_color="#555555", command=self.generar_password)
        btn_gen.pack(side="left")

        # Bloqueamos el cambio de destino al editar para no generar duplicados fantasma
        ctk.CTkLabel(form_frame, text=f"Ubicación original: {origen} (No modificable en edición)", font=("Roboto", 12), text_color="gray").pack(anchor="w", padx=30, pady=(20, 0))

        self.lbl_estado = ctk.CTkLabel(form_frame, text="", font=("Roboto", 14))
        self.lbl_estado.pack(anchor="w", padx=30, pady=5)

        botones_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        botones_frame.pack(anchor="w", padx=30, pady=(0, 30))

        ctk.CTkButton(botones_frame, text="Guardar Cambios", height=45, width=170, command=lambda: self.actualizar_datos(db_id, origen)).pack(side="left", padx=(0, 10))
        ctk.CTkButton(botones_frame, text="Cancelar", height=45, width=100, fg_color="#3b3b3b", hover_color="#555555", command=self.mostrar_lista).pack(side="left")

    def generar_password(self):
        caracteres = string.ascii_letters + string.digits + "!@#$%^&*"
        pwd_segura = "".join(secrets.choice(caracteres) for _ in range(16))
        self.entry_pass.delete(0, 'end')
        self.entry_pass.insert(0, pwd_segura)
        self.entry_pass.configure(show="")

    def guardar_datos(self):
        servicio = self.entry_servicio.get()
        usuario = self.entry_usuario.get()
        password = self.entry_pass.get()
        
        if not servicio or not usuario or not password:
            self.lbl_estado.configure(text="Rellena todos los campos.", text_color="#ff4a4a")
            return
            
        dato = json.dumps({"servicio": servicio, "usuario": usuario, "password": password}).encode('utf-8')
        longitud = len(dato)
        nonce = secrets.token_bytes(24) 
        buffer = ctypes.create_string_buffer(longitud + 16)
        
        if self.core.cifrar_credencial(dato, longitud, nonce, self.clave_simetrica, buffer) != 0:
            self.lbl_estado.configure(text="Error de cifrado.", text_color="#ff4a4a")
            return

        if self.switch_var.get() == 0:
            try:
                conexion = sqlite3.connect("boveda_local.db")
                cursor = conexion.cursor()
                cursor.execute("INSERT INTO credenciales_locales (id_usuario, nonce_hex, datos_cifrados_hex) VALUES (?, ?, ?)",(self.usuario_actual, nonce.hex(), buffer.raw.hex()))
                conexion.commit()
                conexion.close()
                self.lbl_estado.configure(text="¡Guardado Localmente 🏠!", text_color="#4aff6b")
                self.after(1000, self.mostrar_lista)
            except Exception as e:
                self.lbl_estado.configure(text="Error guardando en disco.", text_color="#ff4a4a")
        else:
            try:
                res = requests.post(f"{URL_SERVIDOR}/api/sync", json={"id_usuario": self.usuario_actual, "nonce_hex": nonce.hex(), "datos_cifrados_hex": buffer.raw.hex()}, timeout=3)
                if res.status_code == 200:
                    self.lbl_estado.configure(text="¡Sincronizado en la Nube ☁️!", text_color="#5cacee")
                    self.after(1000, self.mostrar_lista)
            except requests.exceptions.ConnectionError:
                self.lbl_estado.configure(text="Error de red.", text_color="#ff4a4a")

    def actualizar_datos(self, db_id, origen):
        servicio = self.entry_servicio.get()
        usuario = self.entry_usuario.get()
        password = self.entry_pass.get()
        
        if not servicio or not usuario or not password:
            self.lbl_estado.configure(text="Rellena todos los campos.", text_color="#ff4a4a")
            return
            
        dato = json.dumps({"servicio": servicio, "usuario": usuario, "password": password}).encode('utf-8')
        longitud = len(dato)
        nonce = secrets.token_bytes(24) 
        buffer = ctypes.create_string_buffer(longitud + 16)
        
        if self.core.cifrar_credencial(dato, longitud, nonce, self.clave_simetrica, buffer) != 0:
            self.lbl_estado.configure(text="Error de cifrado.", text_color="#ff4a4a")
            return

        if "Local" in origen:
            try:
                conexion = sqlite3.connect("boveda_local.db")
                cursor = conexion.cursor()
                cursor.execute("UPDATE credenciales_locales SET nonce_hex = ?, datos_cifrados_hex = ? WHERE id = ?", (nonce.hex(), buffer.raw.hex(), db_id))
                conexion.commit()
                conexion.close()
                self.lbl_estado.configure(text="¡Actualizado Localmente 🏠!", text_color="#4aff6b")
                self.after(1000, self.mostrar_lista)
            except Exception as e:
                self.lbl_estado.configure(text="Error actualizando.", text_color="#ff4a4a")
        else:
            try:
                res = requests.put(f"{URL_SERVIDOR}/api/sync/{self.usuario_actual}/{db_id}", json={"nonce_hex": nonce.hex(), "datos_cifrados_hex": buffer.raw.hex()}, timeout=3)
                if res.status_code == 200:
                    self.lbl_estado.configure(text="¡Actualizado en la Nube ☁️!", text_color="#5cacee")
                    self.after(1000, self.mostrar_lista)
            except requests.exceptions.ConnectionError:
                self.lbl_estado.configure(text="Error de red.", text_color="#ff4a4a")

if __name__ == "__main__":
    app = VaultApp()
    app.mainloop()