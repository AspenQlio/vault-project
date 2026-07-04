from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os

# Configuración de Base de Datos (Ajusta tu URL de Neon aquí)
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelos de Base de Datos
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    auth_hash = Column(String)

class Credential(Base):
    __tablename__ = "credentials"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    nonce_hex = Column(String)
    encrypted_data_hex = Column(String)

Base.metadata.create_all(bind=engine)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Modelos Pydantic para las peticiones
class RegisterRequest(BaseModel):
    username: str
    auth_hash: str

class LoginRequest(BaseModel):
    username: str
    auth_hash: str

class SyncRequest(BaseModel):
    user_id: str
    nonce_hex: str
    encrypted_data_hex: str

class UpdateHashRequest(BaseModel):
    username: str
    old_auth_hash: str
    new_auth_hash: str

# Endpoints
@app.post("/api/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    new_user = User(username=req.username, auth_hash=req.auth_hash)
    db.add(new_user)
    db.commit()
    return {"message": "User registered successfully"}

@app.post("/api/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or user.auth_hash != req.auth_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"message": "Login successful"}

@app.post("/api/sync")
def sync_credential(req: SyncRequest, db: Session = Depends(get_db)):
    new_cred = Credential(user_id=req.user_id, nonce_hex=req.nonce_hex, encrypted_data_hex=req.encrypted_data_hex)
    db.add(new_cred)
    db.commit()
    return {"message": "Credential synced"}

@app.get("/api/sync/{username}")
def get_credentials(username: str, db: Session = Depends(get_db)):
    creds = db.query(Credential).filter(Credential.user_id == username).all()
    return {"credentials": [{"id": c.id, "nonce_hex": c.nonce_hex, "encrypted_data_hex": c.encrypted_data_hex} for c in creds]}

@app.delete("/api/sync/{username}/{cred_id}")
def delete_credential(username: str, cred_id: int, db: Session = Depends(get_db)):
    cred = db.query(Credential).filter(Credential.id == cred_id, Credential.user_id == username).first()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    db.delete(cred)
    db.commit()
    return {"message": "Credential deleted"}

@app.put("/api/update_hash")
def update_hash(req: UpdateHashRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or user.auth_hash != req.old_auth_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user.auth_hash = req.new_auth_hash
    db.commit()
    return {"message": "Master password updated successfully"}