# Task API

A simple REST API built with **Python**, **FastAPI**, **PostgreSQL**, **Docker**, and **Uvicorn** for managing a to-do list. The API supports full CRUD operations with persistent storage in Postgres, and the entire stack (API + database) starts with a single `docker compose up`.

> This project originally used SQLite (see [Database](#database) below for the migration history) and has since moved to Postgres running in its own Docker container with a persistent volume.

---

## Features

- ✅ Create, Read, Update, and Delete tasks
- ✅ Persistent storage using PostgreSQL, running in Docker with a named volume
- ✅ One-command startup for the full stack (`docker compose up`) — no local Python or Postgres install required
- ✅ Input validation for task titles
- ✅ Health check endpoint that verifies database connectivity
- ✅ Interactive Swagger UI documentation
- ✅ FastAPI automatic OpenAPI documentation

---

## Technologies Used

- Python 3.x
- FastAPI
- PostgreSQL
- psycopg (PostgreSQL driver)
- Docker & Docker Compose
- Uvicorn

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API information |
| GET | `/health` | Health check (verifies the API can reach the database) |
| GET | `/tasks` | List all tasks |
| GET | `/tasks/{id}` | Retrieve a task by ID |
| POST | `/tasks` | Create a task |
| PUT | `/tasks/{id}` | Update a task |
| DELETE | `/tasks/{id}` | Delete a task |
| POST | `/reset` | Wipe all tasks and re-seed the three example tasks |

---

## Quick Start (recommended): run the whole stack with one command

You only need Docker installed — no local Python, no local Postgres install.

```bash
git clone https://github.com/EmmanuelOmonua/todo-api.git
cd todo-api
cp .env.example .env
docker compose up
```

That's it. This one command builds the API image, starts a Postgres container with a persistent volume, waits for the database to be healthy, then starts the API. The API is available at `http://localhost:8000`, and it comes pre-seeded with three example tasks.

Verify it worked:

```bash
curl http://localhost:8000/tasks
```

To stop everything:

```bash
docker compose down
```

This stops and removes the containers but **keeps the database volume**, so your data survives. Run `docker compose up` again and your tasks will still be there. If you ever want a completely clean slate (wipe the database too), use `docker compose down -v` instead.

---

## Environment Variables

The app reads its database connection string from a `DATABASE_URL` environment variable.

- **`.env.example`** (committed) shows the variable you need to set and its shape.
- **`.env`** (gitignored, never committed) is your real copy — create it by running `cp .env.example .env`.

```
DATABASE_URL=postgres://postgres:dev@localhost:5432/tasks
```

Note: when running via `docker compose up`, the `api` service is actually given its own `DATABASE_URL` directly in `compose.yaml` (pointing at hostname `db`, the Postgres service name inside Docker's internal network) — Docker Compose containers reach each other by service name, not `localhost`. The `.env` file's `localhost` version is what you'd use if running `main.py` directly on your machine (outside Docker) against a Postgres container whose port is published to `localhost:5432`.

---

## Running Without Docker (alternative / for local development)

If you'd rather run the API directly on your machine and only use Docker for Postgres:

### Clone the repository

```bash
git clone https://github.com/EmmanuelOmonua/todo-api.git
cd todo-api
```

### Create and activate a virtual environment

**Windows**

```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux**

```bash
python -m venv venv
source venv/bin/activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Start Postgres in Docker (just the database)

```bash
docker run --name taskdb -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=tasks -p 5432:5432 -v taskdata:/var/lib/postgresql/data -d postgres:15
```

### Set up your `.env`

```bash
cp .env.example .env
```

### Start the server

```bash
uvicorn main:app --reload
```

The server will start at `http://localhost:8000`.

---

### Verify the Database Container Directly

You can inspect the running Postgres container and access the SQL prompt using `psql`:

```bash
docker exec -it taskdb psql -U postgres -d tasks -c "\dt"
docker exec -it taskdb psql -U postgres -d tasks -c "SELECT * FROM tasks;"
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

The API now runs on **PostgreSQL** rather than SQLite (see [SQLite Exploration](#sqlite-exploration) and [AI vs me](#ai-vs-me) below for the earlier SQLite stage of this project). Postgres runs as its own container defined in `compose.yaml`, with a named Docker volume (`taskdata`) mounted at Postgres's data directory — so task data survives API restarts, container restarts, and even full container removal (`docker compose down`, without `-v`).

On startup, the application automatically:

- Creates the `tasks` table if it does not already exist.
- Seeds the database with three example tasks if the table is empty.

Because Postgres is now a separate service from the API (rather than a single file the process reads and writes directly, like SQLite was), the database can be restarted or rebuilt independently of the API, and the API simply reconnects to it rather than losing data along with an in-process file.

### Verifying persistence (Stage 5 checkpoint)

To confirm data survives a restart of the whole stack:

```bash
docker compose up -d
curl -X POST http://localhost:8000/tasks -H "Content-Type: application/json" -d '{"title":"Verify persistence"}'
curl http://localhost:8000/tasks          # note the new task is present
docker compose down                       # removes containers, keeps the volume
docker compose up -d                      # fresh containers, same volume
curl http://localhost:8000/tasks          # the task is still there
```

I ran through this exact sequence: created a task, tore down the containers with `docker compose down`, brought the stack back up with `docker compose up`, and confirmed with `GET /tasks` that the task I'd created was still present — along with the three seeded tasks. This confirms the data lives in the `taskdata` Docker volume, not in the container or the API process itself.

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

### Example with response headers (`curl -i`)

```bash
$ curl -i http://localhost:8000/tasks
HTTP/1.1 200 OK
date: Thu, 23 Jul 2026 00:00:00 GMT
server: uvicorn
content-length: 178
content-type: application/json

[{"id":1,"title":"Learn FastAPI","done":false},{"id":2,"title":"Build a CRUD API","done":false},{"id":3,"title":"Publish to GitHub","done":false}]
```

---

## Project Structure

```
todo-api/
│
├── main.py
├── compose.yaml
├── Dockerfile
├── .env.example
├── ai-version/
│   ├── main.py
│   └── requirements.txt
├── README.md
├── requirements.txt
├── swagger-screenshot.png
├── sqlite-browser.png
├── postgres-data-screenshot.png   # add: screenshot of Stage 5 psql/GUI output
└── .gitignore
```

`.env` is intentionally **not** listed above — it's gitignored and won't appear in the repository; only `.env.example` is committed.

---

## Screenshot

![Swagger UI](swagger-screenshot.png)

### Database contents (Stage 5)

Screenshot showing the seeded/created rows in Postgres, taken with either `psql` (`\dt` + a `SELECT * FROM tasks;`) or a GUI client like DBeaver, pgAdmin, or TablePlus:

![Postgres tasks table](postgres-data-screenshot.png)

---

## SQLite Exploration

> This section documents Stage 4, before the project migrated from SQLite to Postgres. It's kept for history; the live app now runs on Postgres as described in [Database](#database) above.

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

For Stage 6, I asked Claude to migrate my original in-memory FastAPI task API to use SQLite while keeping the API behavior the same. I placed the AI-generated version in the `ai-version/main.py` folder so it could be compared with my hand-written implementation.

**My prompt:**

> Convert my existing FastAPI task API from using an in-memory Python list to using SQLite. Use Python's built-in `sqlite3` module. Create a `tasks` table with `id`, `title`, and `done` columns if it doesn't exist, and seed three example tasks only if the table is empty. Keep the same CRUD endpoints and preserve the existing API behavior, including the same HTTP status codes (`201`, `200`, `204`, `400`, `404`) and JSON error responses. Use parameterized SQL queries (? placeholders) for safety. Store task data in `tasks.db` so it survives server restarts.

**Running it:** The generated application started successfully, automatically created `tasks.db`, seeded the database only once, and preserved data after restarting the server. I tested all CRUD endpoints and confirmed that task creation, retrieval, updating, deletion, and persistence behaved correctly.

**What it did better:**

- It created helper functions (`get_conn()`, `init_db()`, and `row_to_task()`) that made the database code cleaner and easier to maintain.
- It consistently used parameterized SQL queries, improving readability and preventing SQL injection.
- It converted the SQLite integer values (`0` and `1`) into Python booleans before returning JSON responses, keeping the API output clean.
- During the rematch, Claude improved the implementation by using a single shared SQLite connection protected by a thread lock instead of opening and closing a database connection for every request. This reduced repeated connection overhead while remaining thread-safe.

**What it got wrong or quietly ignored:**

- It preserved additional endpoints from the original AI version (`/stats`, `/reset`, and task filtering), even though they were not required by the assignment specification.
- It seeded different example tasks ("Buy milk" and "Write README") instead of matching the sample data from my project.
- It did not generate a `requirements.txt` file even though the original AI project included one.

**What my prompt forgot to specify:**

- My prompt described the required SQLite migration but did not specify how database connections should be managed, whether helper functions should be created, or whether the original sample tasks needed to remain exactly the same. Because those details were omitted, Claude made its own implementation decisions.

**One rematch:**

After reviewing the generated code, I refined my prompt to request a single shared SQLite connection instead of opening and closing a connection for every request. The regenerated version replaced the repeated connection logic with one shared connection protected by a thread lock, producing cleaner and more efficient database access.

---

## Author

**Emmanuel Omonua**