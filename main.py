import os
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:dev@localhost:5432/tasks")

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1)

class TaskUpdate(BaseModel):
    title: str = Field(None, min_length=1)
    done: bool = Field(None)

app = FastAPI()

def get_db_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Create tasks table if it doesn't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    done BOOLEAN NOT NULL DEFAULT FALSE
                );
            """)
            
            # Check row count
            cur.execute("SELECT COUNT(*) FROM tasks;")
            count = cur.fetchone()["count"]
            
            # Seed 3 tasks only if empty
            if count == 0:
                cur.executemany("""
                    INSERT INTO tasks (title, done) VALUES (%s, %s);
                """, [
                    ("Learn FastAPI", False),
                    ("Build a CRUD API", False),
                    ("Publish to GitHub", False)
                ])
        conn.commit()

@app.on_event("startup")
def startup_event():
    init_db()

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
    return {"status": "ok"}

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