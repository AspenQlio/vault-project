from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, Session, declarative_base

SQLALCHEMY_DATABASE_URL = "sqlite:///./boveda.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UsuarioDB(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    auth_hash = Column(String)

class CredencialDB(Base):
    __tablename__ = "credenciales"
    id = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(String, index=True)
    nonce_hex = Column(String)
    datos_cifrados_hex = Column(String)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Vault Backend API")

class AuthPayload(BaseModel):
    username: str
    auth_hash: str

class VaultPayload(BaseModel):
    id_usuario: str
    nonce_hex: str
    datos_cifrados_hex: str

# NUEVO: Payload exclusivo para actualizaciones (no necesita el id_usuario en el body)
class UpdatePayload(BaseModel):
    nonce_hex: str
    datos_cifrados_hex: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/api/register")
def registrar_usuario(payload: AuthPayload, db: Session = Depends(get_db)):
    usuario_existente = db.query(UsuarioDB).filter(UsuarioDB.username == payload.username).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="El usuario ya existe")
    nuevo_usuario = UsuarioDB(username=payload.username, auth_hash=payload.auth_hash)
    db.add(nuevo_usuario)
    db.commit()
    return {"estado": "exito", "mensaje": "Cuenta creada"}

@app.post("/api/login")
def iniciar_sesion(payload: AuthPayload, db: Session = Depends(get_db)):
    usuario = db.query(UsuarioDB).filter(UsuarioDB.username == payload.username).first()
    if not usuario or usuario.auth_hash != payload.auth_hash:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return {"estado": "exito", "mensaje": "Autenticado"}

@app.post("/api/sync")
def sincronizar_boveda(payload: VaultPayload, db: Session = Depends(get_db)):
    nueva_credencial = CredencialDB(
        id_usuario=payload.id_usuario, nonce_hex=payload.nonce_hex, datos_cifrados_hex=payload.datos_cifrados_hex
    )
    db.add(nueva_credencial)
    db.commit()
    return {"estado": "exito"}

@app.get("/api/sync/{id_usuario}")
def obtener_boveda(id_usuario: str, db: Session = Depends(get_db)):
    credenciales = db.query(CredencialDB).filter(CredencialDB.id_usuario == id_usuario).all()
    if not credenciales:
        return {"estado": "vacio", "credenciales": []}
    lista = [{"id": c.id, "nonce_hex": c.nonce_hex, "datos_cifrados_hex": c.datos_cifrados_hex} for c in credenciales]
    return {"estado": "exito", "credenciales": lista}

@app.delete("/api/sync/{id_usuario}/{cred_id}")
def eliminar_credencial(id_usuario: str, cred_id: int, db: Session = Depends(get_db)):
    credencial = db.query(CredencialDB).filter(CredencialDB.id_usuario == id_usuario, CredencialDB.id == cred_id).first()
    if not credencial:
        raise HTTPException(status_code=404, detail="Elemento no encontrado")
    db.delete(credencial)
    db.commit()
    return {"estado": "exito"}

# --- NUEVA RUTA: ACTUALIZAR CREDENCIAL ---
@app.put("/api/sync/{id_usuario}/{cred_id}")
def actualizar_credencial(id_usuario: str, cred_id: int, payload: UpdatePayload, db: Session = Depends(get_db)):
    credencial = db.query(CredencialDB).filter(CredencialDB.id_usuario == id_usuario, CredencialDB.id == cred_id).first()
    if not credencial:
        raise HTTPException(status_code=404, detail="Elemento no encontrado")
    
    credencial.nonce_hex = payload.nonce_hex
    credencial.datos_cifrados_hex = payload.datos_cifrados_hex
    db.commit()
    print(f"\n[☁️ Servidor] Credencial {cred_id} actualizada para el usuario: {id_usuario}")
    return {"estado": "exito"}