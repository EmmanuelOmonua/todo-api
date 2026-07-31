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

# --- REUSABLE AUTH DEPENDENCY (MIDDLEWARE) ---
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            options={"verify_signature": False, "verify_aud": True},
            audience="authenticated",
            algorithms=["ES256", "HS256"]
        )
        return payload
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
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

app = FastAPI(title="Todo API - Stage 4", lifespan=lifespan)

@app.exception_handler(psycopg.OperationalError)
async def db_exception_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Database connection failed."}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "Invalid or missing task title"}
    )

@app.get("/")
def read_root():
    return {"name": "Task API", "version": "1.0"}

# --- PROTECTED PROFILE ROUTE ---

@app.get("/protected/profile")
def get_profile(user: dict = Depends(get_current_user)):
    return {
        "id": user.get("sub"),
        "email": user.get("email"),
        "created_at": user.get("iat")
    }

# --- PROTECTED TASK ROUTES ---

@app.get("/tasks")
def get_tasks(user: dict = Depends(get_current_user)):
    user_id = user.get("sub")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, done FROM tasks WHERE user_id = %s ORDER BY id ASC;", (user_id,))
            return [{"id": row["id"], "title": row["title"], "done": row["done"]} for row in cur.fetchall()]

@app.get("/tasks/{task_id}")
def get_task(task_id: int, user: dict = Depends(get_current_user)):
    user_id = user.get("sub")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, done FROM tasks WHERE id = %s AND user_id = %s;", (task_id, user_id))
            row = cur.fetchone()
            if row is None:
                return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": f"Task {task_id} not found"})
            return row

@app.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(task_input: TaskCreate, user: dict = Depends(get_current_user)):
    user_id = user.get("sub")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tasks (title, done, user_id) VALUES (%s, %s, %s) RETURNING id;", (task_input.title, False, user_id))
            new_id = cur.fetchone()["id"]
        conn.commit()
    return {"id": new_id, "title": task_input.title, "done": False}

@app.put("/tasks/{task_id}")
def update_task(task_id: int, task_input: TaskUpdate, user: dict = Depends(get_current_user)):
    user_id = user.get("sub")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, done FROM tasks WHERE id = %s AND user_id = %s;", (task_id, user_id))
            row = cur.fetchone()
            if row is None:
                return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": f"Task {task_id} not found"})
            title = task_input.title if task_input.title is not None else row["title"]
            done = task_input.done if task_input.done is not None else row["done"]
            cur.execute("UPDATE tasks SET title = %s, done = %s WHERE id = %s AND user_id = %s;", (title, done, task_id, user_id))
        conn.commit()
    return {"id": task_id, "title": title, "done": done}

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, user: dict = Depends(get_current_user)):
    user_id = user.get("sub")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM tasks WHERE id = %s AND user_id = %s;", (task_id, user_id))
            if cur.fetchone() is None:
                return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": f"Task {task_id} not found"})
            cur.execute("DELETE FROM tasks WHERE id = %s AND user_id = %s;", (task_id, user_id))
        conn.commit()

# --- AUTH ROUTES ---

@app.post("/auth/signup", status_code=status.HTTP_201_CREATED)
def signup(credentials: UserAuth):
    try:
        response = supabase.auth.sign_up({"email": credentials.email, "password": credentials.password})
        if not response.user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Signup failed")
        return {"message": "User registered successfully", "user_id": response.user.id, "email": response.user.email}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.post("/auth/login")
def login(credentials: UserAuth):
    try:
        response = supabase.auth.sign_in_with_password({"email": credentials.email, "password": credentials.password})
        if not response.session:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        return {"access_token": response.session.access_token, "refresh_token": response.session.refresh_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user: dict = Depends(get_current_user)):
    try:
        supabase.auth.sign_out()
        return None
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))