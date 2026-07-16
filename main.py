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
    return tasks

@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    for task in tasks:
        if task["id"] == task_id:
            return task
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": f"Task {task_id} not found"}
    )

@app.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(task_input: TaskCreate):
    new_id = max([t["id"] for t in tasks]) + 1 if tasks else 1

    new_task = {
        "id": new_id,
        "title": task_input.title,
        "done": False
    }
    tasks.append(new_task)
    return new_task

@app.put("/tasks/{task_id}")
def update_task(task_id: int, task_input: TaskUpdate):
    for task in tasks:
        if task["id"] == task_id:
            if task_input.title is not None:
                task["title"] = task_input.title
            if task_input.done is not None:
                task["done"] = task_input.done
            return task
            
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, 
        content={"error": f"Task {task_id} not found"}
    )


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int):
    global tasks
    for i, task in enumerate(tasks):
        if task["id"] == task_id:
            tasks.pop(i)
            return 
            
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, 
        content={"error": f"Task {task_id} not found"}
    )