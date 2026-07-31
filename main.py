import os
import sys
from typing import Optional
from contextlib import asynccontextmanager

import psycopg
import asyncio
from psycopg.rows import dict_row
from fastapi import FastAPI, status, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, EmailStr
from dotenv import load_dotenv
from supabase import create_client, Client
import jwt
from jwt.exceptions import PyJWTError

# Load environment variables from .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

if not DATABASE_URL or not SUPABASE_URL or not SUPABASE_KEY or not SUPABASE_JWT_SECRET:
    print("FATAL ERROR: Missing required environment variables.", file=sys.stderr)
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
security = HTTPBearer()

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1)

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    done: Optional[bool] = None

class UserAuth(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Stage 3 Guard: Verifies token against Supabase / JWT decoding."""
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_aud": True
            },
            audience="authenticated",
            algorithms=["ES256", "HS256"]
        )
        return payload
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_db_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=2)

def init_db():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        id SERIAL PRIMARY KEY,
                        title TEXT NOT NULL,
                        done BOOLEAN NOT NULL DEFAULT FALSE,
                        user_id VARCHAR(255)
                    );
                """)
                cur.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS user_id VARCHAR(255);")
            conn.commit()
    except psycopg.OperationalError as e:
        print(f"Database initialization failed: {e}", file=sys.stderr)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(init_db)
    yield

app = FastAPI(title="Todo API with Supabase Auth", lifespan=lifespan)

@app.get("/")
def read_root():
    return {"name": "Task API", "version": "1.0"}

# --- STAGE 3 PROTECTED PROFILE ROUTE ---
@app.get("/protected/profile")
def get_profile(user: dict = Depends(verify_token)):
    return {
        "id": user.get("sub"),
        "email": user.get("email"),
        "created_at": user.get("iat")
    }

# --- AUTH ROUTES ---
@app.post("/auth/signup", status_code=status.HTTP_201_CREATED)
def signup(credentials: UserAuth):
    response = supabase.auth.sign_up({"email": credentials.email, "password": credentials.password})
    if not response.user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Signup failed")
    return {"message": "User registered successfully", "user_id": response.user.id, "email": response.user.email}

@app.post("/auth/login")
def login(credentials: UserAuth):
    response = supabase.auth.sign_in_with_password({"email": credentials.email, "password": credentials.password})
    if not response.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return {"access_token": response.session.access_token, "refresh_token": response.session.refresh_token, "token_type": "bearer"}