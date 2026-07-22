import sqlite3

# main.py
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse                         
from fastapi.exceptions import RequestValidationError                
from pydantic import BaseModel, Field

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1)

class TaskUpdate(BaseModel):
    title: str = Field(None, min_length=1)
    done: bool = Field(None)

tasks = [
    {"id": 1, "title": "Learn FastAPI", "done": False},
    {"id": 2, "title": "Build a CRUD API", "done": False},
    {"id": 3, "title": "Publish to Github", "done": False},
]

app = FastAPI()

conn = sqlite3.connect("tasks.db", check_same_thread=False)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    done INTEGER NOT NULL
)
""")

conn.commit()

# Check how many rows are in the table
cursor.execute("SELECT COUNT(*) FROM tasks")
count = cursor.fetchone()[0]

# Seed only if the table is empty
if count == 0:
    cursor.executemany("""
        INSERT INTO tasks (title, done)
        VALUES (?, ?)
    """, [
        ("Learn FastAPI", 0),
        ("Build a CRUD API", 0),
        ("Publish to GitHub", 0)
    ])

    conn.commit()

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
    cursor.execute("SELECT * FROM tasks")
    rows = cursor.fetchall()

    return [
        {
            "id": row["id"],
            "title": row["title"],
            "done": bool(row["done"])
        }
        for row in rows
    ]

@app.get("/tasks/{task_id}")
def get_task(task_id: int):

    cursor.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    )

    row = cursor.fetchone()

    if row is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": f"Task {task_id} not found"}
        )

    return {
        "id": row["id"],
        "title": row["title"],
        "done": bool(row["done"])
    }

@app.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(task_input: TaskCreate):

    cursor.execute(
        """
        INSERT INTO tasks (title, done)
        VALUES (?, ?)
        """,
        (task_input.title, 0)
    )

    conn.commit()

    new_id = cursor.lastrowid

    return {
        "id": new_id,
        "title": task_input.title,
        "done": False
    }

@app.put("/tasks/{task_id}")
def update_task(task_id: int, task_input: TaskUpdate):

    cursor.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    )

    row = cursor.fetchone()

    if row is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": f"Task {task_id} not found"}
        )

    title = row["title"]
    done = bool(row["done"])

    if task_input.title is not None:
        title = task_input.title

    if task_input.done is not None:
        done = task_input.done

    cursor.execute(
        """
        UPDATE tasks
        SET title = ?, done = ?
        WHERE id = ?
        """,
        (title, int(done), task_id)
    )

    conn.commit()

    return {
        "id": task_id,
        "title": title,
        "done": done
    }


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int):

    cursor.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    )

    if cursor.fetchone() is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": f"Task {task_id} not found"}
        )

    cursor.execute(
        "DELETE FROM tasks WHERE id = ?",
        (task_id,)
    )

    conn.commit()

@app.post("/reset")
def reset_tasks():

    cursor.execute("DELETE FROM tasks")

    cursor.executemany(
        """
        INSERT INTO tasks (title, done)
        VALUES (?, ?)
        """,
        [
            ("Learn FastAPI", 0),
            ("Build a CRUD API", 0),
            ("Publish to GitHub", 0),
        ]
    )

    conn.commit()

    return {"message": "Tasks reset successfully"}