from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from typing import Union

SQLALCHEMY_DATABASE_URL = "sqlite:///./vault.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    auth_hash = Column(String)

class CredentialDB(Base):
    __tablename__ = "credentials"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    nonce_hex = Column(String)
    encrypted_data_hex = Column(String)

class Credencial(Base):
    __tablename__ = "credenciales"
    id = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(Integer, index=True)
    sitio = Column(String, index=True)
    usuario_crypto = Column(String)
    pass_crypto = Column(String)
    nonce = Column(String)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Vault Backend API")

class AuthPayload(BaseModel):
    username: str
    auth_hash: str

class VaultPayload(BaseModel):
    user_id: str
    nonce_hex: str
    encrypted_data_hex: str

class CredencialSync(BaseModel):
    id_usuario: int
    sitio: str
    usuario_hex: str
    datos_cifrados_hex: str
    nonce_hex: str

# New: update-only payload (does not need the user_id in the body)
class UpdatePayload(BaseModel):
    nonce_hex: str
    encrypted_data_hex: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/api/register")
def register_user(payload: AuthPayload, db: Session = Depends(get_db)):
    existing_user = db.query(UserDB).filter(UserDB.username == payload.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    new_user = UserDB(username=payload.username, auth_hash=payload.auth_hash)
    db.add(new_user)
    db.commit()
    return {"status": "success", "message": "Account created"}

@app.post("/api/login")
def login_user(payload: AuthPayload, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.username == payload.username).first()
    if not user or user.auth_hash != payload.auth_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"status": "success", "message": "Authenticated"}

@app.post("/api/sync")
def sync_vault(payload: Union[VaultPayload, CredencialSync], db: Session = Depends(get_db)):
    if isinstance(payload, CredencialSync):
        existente = db.query(Credencial).filter(
            Credencial.id_usuario == payload.id_usuario,
            Credencial.sitio == payload.sitio,
        ).first()

        if existente:
            existente.usuario_crypto = payload.usuario_hex
            existente.pass_crypto = payload.datos_cifrados_hex
            existente.nonce = payload.nonce_hex
            db.commit()
            return {"mensaje": "Actualizado", "estado": "ok"}

        nueva_credencial = Credencial(
            id_usuario=payload.id_usuario,
            sitio=payload.sitio,
            usuario_crypto=payload.usuario_hex,
            pass_crypto=payload.datos_cifrados_hex,
            nonce=payload.nonce_hex,
        )
        db.add(nueva_credencial)
        db.commit()
        return {"mensaje": "Creado", "estado": "ok"}

    new_credential = CredentialDB(
        user_id=payload.user_id, nonce_hex=payload.nonce_hex, encrypted_data_hex=payload.encrypted_data_hex
    )
    db.add(new_credential)
    db.commit()
    return {"status": "success"}

@app.get("/api/sync/{user_id}")
def get_vault(user_id: str, db: Session = Depends(get_db)):
    credentials = db.query(CredentialDB).filter(CredentialDB.user_id == user_id).all()
    if not credentials:
        return {"status": "empty", "credentials": []}
    credential_list = [{"id": c.id, "nonce_hex": c.nonce_hex, "encrypted_data_hex": c.encrypted_data_hex} for c in credentials]
    return {"status": "success", "credentials": credential_list}

@app.delete("/api/sync/{user_id}/{cred_id}")
def delete_credential(user_id: str, cred_id: int, db: Session = Depends(get_db)):
    credential = db.query(CredentialDB).filter(CredentialDB.user_id == user_id, CredentialDB.id == cred_id).first()
    if not credential:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(credential)
    db.commit()
    return {"status": "success"}

# --- New route: update credential ---
@app.put("/api/sync/{user_id}/{cred_id}")
def update_credential(user_id: str, cred_id: int, payload: UpdatePayload, db: Session = Depends(get_db)):
    credential = db.query(CredentialDB).filter(CredentialDB.user_id == user_id, CredentialDB.id == cred_id).first()
    if not credential:
        raise HTTPException(status_code=404, detail="Item not found")
    
    credential.nonce_hex = payload.nonce_hex
    credential.encrypted_data_hex = payload.encrypted_data_hex
    db.commit()
    print(f"\n[ Server] Credential {cred_id} updated for user: {user_id}")
    return {"status": "success"}
