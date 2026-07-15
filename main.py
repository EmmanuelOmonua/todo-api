# main.py
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1)

tasks = [
    {"id": 1, "title": "Learn FastAPI", "done": False},
    {"id": 2, "title": "Build a CRUD API", "done": False},
    {"id": 3, "title": "Publish to Github", "done": False},
]

app = FastAPI()

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
    return tasks

@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    for task in tasks:
        if task["id"] == task_id:
            return task
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Task {task_id} not found"
    )

@app.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(task_input: TaskCreate):
    # Calculate the next free ID dynamically
    new_id = max([t["id"] for t in tasks]) + 1 if tasks else 1

    new_task = {
        "id": new_id,
        "title": task_input.title,
        "done": False
    }
    tasks.append(new_task)
    return new_task