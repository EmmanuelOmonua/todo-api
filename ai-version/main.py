import sqlite3
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

DB_PATH = Path(__file__).resolve().parent / "tasks.db"

# A single shared connection is reused for every request instead of opening
# and closing a new one each time. FastAPI runs sync endpoints in a
# threadpool, so check_same_thread=False lets the connection be used from
# whichever worker thread handles a given request, and a lock serializes
# access since a single sqlite3 connection isn't safe for concurrent use
# from multiple threads at once.
conn: Optional[sqlite3.Connection] = None
db_lock = threading.Lock()


class TaskCreate(BaseModel):
    # title is Optional here (not required str) so a missing title reaches our
    # own validation and returns 400 with our error shape, instead of FastAPI's
    # automatic 422 response.
    title: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None


def init_db():
    global conn
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    with db_lock:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                done INTEGER NOT NULL
            )
            """
        )
        conn.commit()

        count = conn.execute("SELECT COUNT(*) AS count FROM tasks").fetchone()["count"]
        if count == 0:
            conn.executemany(
                "INSERT INTO tasks (id, title, done) VALUES (?, ?, ?)",
                [
                    (1, "Buy milk", 0),
                    (2, "Write README", 0),
                    (3, "Learn FastAPI", 1),
                ],
            )
            conn.commit()


def row_to_task(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "title": row["title"], "done": bool(row["done"])}


app = FastAPI(title="Task API", version="1.0")


@app.on_event("startup")
def on_startup():
    init_db()


@app.on_event("shutdown")
def on_shutdown():
    if conn is not None:
        conn.close()


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException):
    # Assignment spec wants {"error": "..."} instead of FastAPI's default {"detail": "..."}
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.get("/", summary="API info")
def root():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health", summary="Health check")
def health():
    return {"status": "ok"}


@app.get("/tasks", summary="List all tasks (optionally filter by done/search)")
def list_tasks(done: Optional[bool] = None, search: Optional[str] = None):
    query = "SELECT id, title, done FROM tasks WHERE 1=1"
    params: list = []
    if done is not None:
        query += " AND done = ?"
        params.append(1 if done else 0)
    if search:
        query += " AND LOWER(title) LIKE ?"
        params.append(f"%{search.lower()}%")
    with db_lock:
        rows = conn.execute(query, params).fetchall()
    return [row_to_task(row) for row in rows]


@app.get("/stats", summary="Task counts: total/done/open")
def stats():
    with db_lock:
        total = conn.execute("SELECT COUNT(*) AS c FROM tasks").fetchone()["c"]
        done_count = conn.execute("SELECT COUNT(*) AS c FROM tasks WHERE done = 1").fetchone()["c"]
    return {"total": total, "done": done_count, "open": total - done_count}


@app.post("/reset", summary="Restore the 3 example tasks")
def reset_tasks():
    with db_lock:
        conn.execute("DELETE FROM tasks")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'tasks'")
        conn.executemany(
            "INSERT INTO tasks (id, title, done) VALUES (?, ?, ?)",
            [
                (1, "Buy milk", 0),
                (2, "Write README", 0),
                (3, "Learn FastAPI", 1),
            ],
        )
        conn.commit()
    return {"message": "Tasks reset to the 3 example tasks"}


@app.get("/tasks/{task_id}", summary="Get one task by id")
def get_task(task_id: int):
    with db_lock:
        row = conn.execute(
            "SELECT id, title, done FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return row_to_task(row)


@app.post("/tasks", status_code=201, summary="Create a new task")
def create_task(body: TaskCreate):
    if not body.title or not body.title.strip():
        raise HTTPException(status_code=400, detail="title is required and cannot be empty")

    with db_lock:
        cursor = conn.execute(
            "INSERT INTO tasks (title, done) VALUES (?, ?)", (body.title, 0)
        )
        conn.commit()
        new_id = cursor.lastrowid
        row = conn.execute(
            "SELECT id, title, done FROM tasks WHERE id = ?", (new_id,)
        ).fetchone()
    return row_to_task(row)


@app.put("/tasks/{task_id}", summary="Update a task's title and/or done status")
def update_task(task_id: int, body: TaskUpdate):
    if body.title is None and body.done is None:
        raise HTTPException(status_code=400, detail="provide at least title or done")

    if body.title is not None and not body.title.strip():
        raise HTTPException(status_code=400, detail="title cannot be empty")

    with db_lock:
        row = conn.execute(
            "SELECT id, title, done FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        new_title = body.title if body.title is not None else row["title"]
        new_done = (1 if body.done else 0) if body.done is not None else row["done"]

        conn.execute(
            "UPDATE tasks SET title = ?, done = ? WHERE id = ?",
            (new_title, new_done, task_id),
        )
        conn.commit()

        updated = conn.execute(
            "SELECT id, title, done FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return row_to_task(updated)


@app.delete("/tasks/{task_id}", status_code=204, summary="Delete a task")
def delete_task(task_id: int):
    with db_lock:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return