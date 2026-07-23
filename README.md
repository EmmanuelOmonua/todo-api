# Task API

A simple REST API built with **Python**, **FastAPI**, **SQLite**, and **Uvicorn** for managing a to-do list. The API supports full CRUD operations with persistent storage using SQLite, allowing task data to remain available after the server is restarted.

---

## Features

- ✅ Create, Read, Update, and Delete tasks
- ✅ Persistent storage using SQLite
- ✅ Input validation for task titles
- ✅ Health check endpoint
- ✅ Interactive Swagger UI documentation
- ✅ FastAPI automatic OpenAPI documentation

---

## Technologies Used

- Python 3.x
- FastAPI
- SQLite
- sqlite3
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
pip install -r requirements.txt
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

## Database

The API uses SQLite because it is a lightweight, serverless database stored in a single file (`tasks.db`). It requires zero database setup, is included with Python through the `sqlite3` module, and allows task data to survive application restarts.

On first startup, the application automatically:

- Creates the `tasks` table if it does not already exist.
- Seeds the database with three example tasks if the table is empty.

Because the API and SQLite database share the same database file, changes made through the API or directly in SQLite are immediately reflected without restarting the server.

The database file (`tasks.db`) is created automatically the first time the application starts and is not committed to the repository.

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
    "done": false
  },
  {
    "id": 2,
    "title": "Build a CRUD API",
    "done": false
  },
  {
    "id": 3,
    "title": "Publish to GitHub",
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
├── requirements.txt
├── swagger-screenshot.png
└── .gitignore
```

---

## Screenshot

![Swagger UI](swagger-screenshot.png)

---

## SQLite Exploration

During Stage 4, I explored the SQLite database directly using **DB Browser for SQLite**.

### Example SQL Query

```sql
SELECT COUNT(*) FROM tasks;
```

## SQLite Database

![SQLite Database](sqlite-browser.png)

### Result

This query returned the total number of tasks stored in the database. I used it to verify the number of records in the `tasks` table before modifying the data through SQL.

I also verified that changes made directly in the SQLite database were immediately reflected through the API without restarting the FastAPI server.

---

## AI vs me

For the bonus stage, I wrote a prompt from memory and asked an AI assistant to build the same API. The AI's code lives in `ai-version/main.py`, untouched from what it generated, so it can be compared against my hand-built version above.

**My prompt:**

> From memory, I asked the AI to build a REST API for a simple to-do list using Python and FastAPI. The API should store tasks in memory only, support CRUD operations, include a health check endpoint, validate that task titles are not blank, return appropriate HTTP status codes, and generate Swagger documentation automatically. I also asked it to avoid using a database.

**Running it:** I ran the same API requests against the AI's version on port 8001, including creating a task, retrieving a task, updating a task, deleting a task, and testing invalid requests. The AI implementation returned the expected status codes and JSON responses, including `404` with `{"error": ...}` for an unknown task, `400` with `{"error": ...}` for an invalid POST request, and `201` for a successful task creation.

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
