# Task API

A simple REST API built with **Python**, **FastAPI**, and **Uvicorn** for managing a to-do list. The API supports full CRUD operations and stores tasks in memory.

---

## Features

- ✅ Create, Read, Update, and Delete tasks
- ✅ Input validation for task titles
- ✅ Health check endpoint
- ✅ Interactive Swagger UI documentation
- ✅ FastAPI automatic OpenAPI documentation

---

## Technologies Used

- Python 3.x
- FastAPI
- Uvicorn

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API information |
| GET | `/health` | Health check |
| GET | `/tasks` | List all tasks |
| GET | `/tasks/{id}` | Retrieve a task by ID |
| POST | `/tasks` | Create a task |
| PUT | `/tasks/{id}` | Update a task |
| DELETE | `/tasks/{id}` | Delete a task |

---

## Installation

### Clone the repository

```bash
git clone https://github.com/EmmanuelOmonua/todo-api.git
cd todo-api
```

### Create a virtual environment

```bash
python -m venv venv
```

### Activate the virtual environment

**Windows**

```bash
venv\Scripts\activate
```

**macOS/Linux**

```bash
source venv/bin/activate
```

### Install dependencies

```bash
pip install fastapi uvicorn
```

### Start the server

```bash
uvicorn main:app --reload
```

The server will start at:

```
http://localhost:8000
```

---

## API Documentation

FastAPI automatically generates interactive documentation.

Open:

```
http://localhost:8000/docs
```

---

## Example Request

```bash
curl http://localhost:8000/tasks
```

Example response:

```json
[
  {
    "id": 1,
    "title": "Learn FastAPI",
    "done": true
  },
  {
    "id": 3,
    "title": "Publish to Github",
    "done": false
  }
]
```

---

## Project Structure

```
todo-api/
│
├── main.py
├── ai-version/
│   ├── main.py
│   └── requirements.txt
├── README.md
├── swagger-screenshot.png
└── venv/
```

---

## Screenshot

![Swagger UI](swagger-screenshot.png)

---

## AI vs me

For the bonus stage, I wrote a prompt from memory and asked an AI assistant to build the same API. The AI's code lives in `ai-version/main.py`, untouched from what it generated, so it can be compared against my hand-built version above.

**My prompt:**

> From memory, I asked the AI to build a REST API for a simple to-do list using Python and FastAPI. The API should store tasks in memory only, support CRUD operations, include a health check endpoint, validate that task titles are not blank, return appropriate HTTP status codes, and generate Swagger documentation automatically. I also asked it to avoid using a database.

**Running it:** I ran my Stage 4 checkpoint curls against the AI's version on port 8001. All of them returned the expected status codes and JSON — `404` with `{"error": ...}` for an unknown task, `400` with `{"error": ...}` for an empty POST body, `201` for a valid create.

**What it did better:**

- Used a single global exception handler (`@app.exception_handler(HTTPException)`) so every route that raises `HTTPException` automatically gets formatted as `{"error": ...}`, instead of repeating a `JSONResponse` block in every route like I did.
- Gave each validation error a specific message (e.g. `"title is required and cannot be empty"`) rather than one generic message for every failure.
- Added `summary=` text to each endpoint, which shows up in Swagger UI.
- Added extra endpoints I didn't ask for: `/stats`, `/reset`, and `?done=`/`?search=` filtering on `/tasks`.

**What it got wrong or quietly ignored:**

- It matched the `{"error": ...}` response format on the first try, so I didn't need to change my prompt for that requirement.
- It tracks new task IDs with a `next_id` counter that only ever increases, while I recompute `max(id) + 1` each time. My prompt never specified how IDs should behave after a task is deleted, so we ended up with different implementations.
- It added extra functionality that I didn't ask for, including `/stats`, `/reset`, and filtering tasks with `?done=` and `?search=`. These features work well, but they weren't part of the assignment requirements.

**What my prompt forgot to specify:**

- My prompt focused on the required functionality but didn't specify every implementation detail. It didn't mention how task IDs should be generated after deletions, whether additional helper endpoints should be included, or whether filtering tasks should be supported. Because of that, the AI made its own design choices in those areas.

**One rematch:**

After comparing the AI's solution with my own, I updated my prompt to explicitly state that only the required assignment endpoints should be implemented. The regenerated version removed the extra helper endpoints and more closely matched the assignment specification.

---

## Author

**Emmanuel Omonua**
