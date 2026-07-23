import os
import sys
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Rule 1: Validate DATABASE_URL on startup
if not DATABASE_URL:
    print("FATAL ERROR: DATABASE_URL environment variable is missing or empty.", file=sys.stderr)
    sys.exit(1)

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1)

class TaskUpdate(BaseModel):
    title: str = Field(None, min_length=1)
    done: bool = Field(None)

app = FastAPI()

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
        "endpoints": ["/tasks"]
    }

@app.get("/health")
def health_check():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        return {"status": "ok", "database": "connected"}
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "database": "disconnected"}
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