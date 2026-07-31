import os
import sys
from typing import Optional
from contextlib import asynccontextmanager

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, EmailStr
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Validate required environment variables on startup
if not DATABASE_URL:
    print("FATAL ERROR: DATABASE_URL environment variable is missing or empty.", file=sys.stderr)
    sys.exit(1)

if not SUPABASE_URL or not SUPABASE_KEY:
    print("FATAL ERROR: SUPABASE_URL or SUPABASE_KEY environment variable is missing.", file=sys.stderr)
    sys.exit(1)

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1)

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    done: Optional[bool] = None

class UserAuth(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Todo API with Supabase Auth", lifespan=lifespan)

def get_db_connection():
    # Will raise psycopg.OperationalError if database is unreachable
    # Adding connect_timeout=2 forces psycopg to fail fast if DB is down
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=2)

def init_db():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        id SERIAL PRIMARY KEY,
                        title TEXT NOT NULL,
                        done BOOLEAN NOT NULL DEFAULT FALSE
                    );
                """)
                
                cur.execute("SELECT COUNT(*) FROM tasks;")
                count = cur.fetchone()["count"]
                
                if count == 0:
                    cur.executemany("""
                        INSERT INTO tasks (title, done) VALUES (%s, %s);
                    """, [
                        ("Learn FastAPI", False),
                        ("Build a CRUD API", False),
                        ("Publish to GitHub", False)
                    ])
            conn.commit()
    except psycopg.OperationalError as e:
        print(f"Database initialization failed: {e}", file=sys.stderr)
        # Allow startup to finish so app can return 500 status on route calls

@app.on_event("startup")
def startup_event():
    init_db()

# Catch generic Database errors across API calls
@app.exception_handler(psycopg.OperationalError)
async def db_exception_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Database connection failed. Please ensure PostgreSQL is running."}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "Invalid or missing task title"}
    )

@app.get("/")
def read_root():
    return {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks", "/health"]
    }

@app.get("/health")
def health_check():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        return {"status": "ok", "database": "ok"}
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error",
                "database": "unreachable",
                "detail": str(e)
            }
        )

@app.get("/tasks")
def get_tasks():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, done FROM tasks ORDER BY id ASC;")
            return cur.fetchall()

@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, done FROM tasks WHERE id = %s;", (task_id,))
            row = cur.fetchone()

            if row is None:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"error": f"Task {task_id} not found"}
                )

            return row

@app.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(task_input: TaskCreate):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tasks (title, done) VALUES (%s, %s) RETURNING id;",
                (task_input.title, False)
            )
            new_id = cur.fetchone()["id"]
        conn.commit()

    return {
        "id": new_id,
        "title": task_input.title,
        "done": False
    }

@app.put("/tasks/{task_id}")
def update_task(task_id: int, task_input: TaskUpdate):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, done FROM tasks WHERE id = %s;", (task_id,))
            row = cur.fetchone()

            if row is None:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"error": f"Task {task_id} not found"}
                )

            title = row["title"]
            done = row["done"]

            if task_input.title is not None:
                title = task_input.title

            if task_input.done is not None:
                done = task_input.done

            cur.execute(
                "UPDATE tasks SET title = %s, done = %s WHERE id = %s;",
                (title, done, task_id)
            )
        conn.commit()

    return {
        "id": task_id,
        "title": title,
        "done": done
    }

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM tasks WHERE id = %s;", (task_id,))
            if cur.fetchone() is None:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"error": f"Task {task_id} not found"}
                )

            cur.execute("DELETE FROM tasks WHERE id = %s;", (task_id,))
        conn.commit()

@app.post("/reset")
def reset_tasks():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE tasks RESTART IDENTITY;")
            cur.executemany(
                "INSERT INTO tasks (title, done) VALUES (%s, %s);",
                [
                    ("Learn FastAPI", False),
                    ("Build a CRUD API", False),
                    ("Publish to GitHub", False),
                ]
            )
        conn.commit()

    return {"message": "Tasks reset successfully"}

@app.post("/auth/signup", status_code=status.HTTP_201_CREATED)
def signup(credentials: UserAuth):
    try:
        response = supabase.auth.sign_up({
            "email": credentials.email,
            "password": credentials.password,
        })
        if not response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Signup failed"
            )
        return {
            "message": "User registered successfully",
            "user_id": response.user.id,
            "email": response.user.email
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@app.post("/auth/login")
def login(credentials: UserAuth):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password,
        })
        if not response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "token_type": "bearer"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

@app.post("/auth/logout")
def logout():
    try:
        supabase.auth.sign_out()
        return {"message": "Successfully logged out"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )