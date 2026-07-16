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
├── README.md
├── swagger-screenshot.png
└── venv/
```

---

## Screenshot

![Swagger UI](swagger-screenshot.png)

---

## Author

**Emmanuel Omonua**

Course Project