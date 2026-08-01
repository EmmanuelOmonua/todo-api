"""
Task Management API
--------------------
Production-ready REST API built with FastAPI, PostgreSQL (psycopg3) and
Supabase Auth.

Run with:
    uvicorn main:app --reload
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import httpx
import jwt
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field

# --------------------------------------------------------------------------
# Environment configuration
# --------------------------------------------------------------------------

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

REQUIRED_ENV_VARS = {
    "DATABASE_URL": DATABASE_URL,
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_KEY": SUPABASE_KEY,
    "SUPABASE_JWT_SECRET": SUPABASE_JWT_SECRET,
}

missing = [name for name, value in REQUIRED_ENV_VARS.items() if not value]
if missing:
    # Don't hard-crash on import (useful for docs generation / testing),
    # but surface a loud warning. Actual DB/auth calls will fail clearly.
    print(f"[WARNING] Missing required environment variables: {', '.join(missing)}")

JWT_ALGORITHMS = ["HS256", "ES256"]
JWT_AUDIENCE = "authenticated"

# --------------------------------------------------------------------------
# Database connection pool
# --------------------------------------------------------------------------

pool: Optional[ConnectionPool] = None


def init_db_pool() -> ConnectionPool:
    """Create the psycopg connection pool (dict row factory)."""
    return ConnectionPool(
        conninfo=DATABASE_URL,
        min_size=1,
        max_size=10,
        kwargs={"row_factory": dict_row},
    )


def create_tasks_table() -> None:
    """Create the `tasks` table on startup if it does not already exist."""
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    done BOOLEAN DEFAULT FALSE,
                    user_id VARCHAR(255)
                )
                """
            )
        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    if DATABASE_URL:
        pool = init_db_pool()
        create_tasks_table()
    yield
    if pool:
        pool.close()


# --------------------------------------------------------------------------
# FastAPI app + OpenAPI Bearer auth scheme (for Swagger "Authorize" button)
# --------------------------------------------------------------------------

app = FastAPI(
    title="Task Management API",
    description="A production-ready task management REST API secured with Supabase Auth.",
    version="1.0.0",
    lifespan=lifespan,
)

bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    description="Enter your Supabase access token (JWT).",
    auto_error=False,
)


# --------------------------------------------------------------------------
# Pydantic schemas
# --------------------------------------------------------------------------

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ProfileResponse(BaseModel):
    id: str
    email: Optional[str] = None
    issued_at: Optional[datetime] = None
    created_at: Optional[str] = None


class TaskCreate(BaseModel):
    title: str


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None


class TaskOut(BaseModel):
    id: int
    title: str
    done: bool
    user_id: str


# --------------------------------------------------------------------------
# Auth dependency (JWT verification guard)
# --------------------------------------------------------------------------

class CurrentUser(BaseModel):
    sub: str
    email: Optional[str] = None
    issued_at: Optional[datetime] = None
    raw_claims: dict


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> CurrentUser:
    """
    Reusable security dependency ("guard") that:
      1. Extracts the Bearer token from the Authorization header.
      2. Verifies it against SUPABASE_JWT_SECRET.
      3. Returns the decoded user identity, or raises 401.
    """
    if credentials is None or not credentials.credentials:
        raise _unauthorized()

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=JWT_ALGORITHMS,
            audience=JWT_AUDIENCE,
            options={"verify_aud": True},
        )
    except jwt.PyJWTError:
        # Retry once without audience verification, in case the Supabase
        # project issues tokens without a strict "authenticated" audience.
        try:
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=JWT_ALGORITHMS,
                options={"verify_aud": False},
            )
        except jwt.PyJWTError:
            raise _unauthorized()

    sub = payload.get("sub")
    if not sub:
        raise _unauthorized()

    issued_at = None
    if payload.get("iat"):
        issued_at = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)

    return CurrentUser(
        sub=sub,
        email=payload.get("email"),
        issued_at=issued_at,
        raw_claims=payload,
    )


# --------------------------------------------------------------------------
# Supabase Auth HTTP helpers
# --------------------------------------------------------------------------

def _supabase_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
    }


async def supabase_signup(email: str, password: str) -> dict:
    url = f"{SUPABASE_URL}/auth/v1/signup"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url, headers=_supabase_headers(), json={"email": email, "password": password}
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.json())
    return resp.json()


async def supabase_login(email: str, password: str) -> dict:
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url, headers=_supabase_headers(), json={"email": email, "password": password}
        )
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return resp.json()


async def supabase_logout(access_token: str) -> None:
    url = f"{SUPABASE_URL}/auth/v1/logout"
    headers = _supabase_headers()
    headers["Authorization"] = f"Bearer {access_token}"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers)
    if resp.status_code >= 400 and resp.status_code != 204:
        raise HTTPException(status_code=resp.status_code, detail="Logout failed")


# --------------------------------------------------------------------------
# Root endpoint
# --------------------------------------------------------------------------

@app.get("/", status_code=status.HTTP_200_OK, tags=["Root"])
async def root():
    return {"name": "Task Management API", "version": "1.0.0"}


# --------------------------------------------------------------------------
# Auth endpoints
# --------------------------------------------------------------------------

@app.post("/auth/signup", status_code=status.HTTP_201_CREATED, tags=["Auth"])
async def signup(payload: SignupRequest):
    result = await supabase_signup(payload.email, payload.password)
    return result


@app.post("/auth/login", response_model=TokenResponse, status_code=status.HTTP_200_OK, tags=["Auth"])
async def login(payload: LoginRequest):
    result = await supabase_login(payload.email, payload.password)
    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        token_type="bearer",
    )


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["Auth"])
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    current_user: CurrentUser = Depends(get_current_user),
):
    await supabase_logout(credentials.credentials)
    return None


# --------------------------------------------------------------------------
# Protected profile endpoint
# --------------------------------------------------------------------------

@app.get("/protected/profile", response_model=ProfileResponse, status_code=status.HTTP_200_OK, tags=["Protected"])
async def get_profile(current_user: CurrentUser = Depends(get_current_user)):
    return ProfileResponse(
        id=current_user.sub,
        email=current_user.email,
        issued_at=current_user.issued_at,
        created_at=current_user.raw_claims.get("created_at"),
    )


# --------------------------------------------------------------------------
# Task endpoints (protected, user-isolated)
# --------------------------------------------------------------------------

@app.get("/tasks", response_model=list[TaskOut], status_code=status.HTTP_200_OK, tags=["Tasks"])
async def list_tasks(current_user: CurrentUser = Depends(get_current_user)):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, done, user_id FROM tasks WHERE user_id = %s ORDER BY id",
                (current_user.sub,),
            )
            rows = cur.fetchall()
    return rows


@app.get("/tasks/{task_id}", response_model=TaskOut, status_code=status.HTTP_200_OK, tags=["Tasks"])
async def get_task(task_id: int, current_user: CurrentUser = Depends(get_current_user)):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, done, user_id FROM tasks WHERE id = %s AND user_id = %s",
                (task_id, current_user.sub),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return row


@app.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED, tags=["Tasks"])
async def create_task(payload: TaskCreate, current_user: CurrentUser = Depends(get_current_user)):
    title = payload.title.strip() if payload.title else ""
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Title must not be empty")

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tasks (title, done, user_id)
                VALUES (%s, FALSE, %s)
                RETURNING id, title, done, user_id
                """,
                (title, current_user.sub),
            )
            row = cur.fetchone()
        conn.commit()
    return row


@app.put("/tasks/{task_id}", response_model=TaskOut, status_code=status.HTTP_200_OK, tags=["Tasks"])
async def update_task(
    task_id: int, payload: TaskUpdate, current_user: CurrentUser = Depends(get_current_user)
):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, done, user_id FROM tasks WHERE id = %s AND user_id = %s",
                (task_id, current_user.sub),
            )
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

            new_title = existing["title"]
            if payload.title is not None:
                trimmed = payload.title.strip()
                if not trimmed:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail="Title must not be empty"
                    )
                new_title = trimmed

            new_done = payload.done if payload.done is not None else existing["done"]

            cur.execute(
                """
                UPDATE tasks SET title = %s, done = %s
                WHERE id = %s AND user_id = %s
                RETURNING id, title, done, user_id
                """,
                (new_title, new_done, task_id, current_user.sub),
            )
            row = cur.fetchone()
        conn.commit()
    return row


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Tasks"])
async def delete_task(task_id: int, current_user: CurrentUser = Depends(get_current_user)):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM tasks WHERE id = %s AND user_id = %s RETURNING id",
                (task_id, current_user.sub),
            )
            deleted = cur.fetchone()
        conn.commit()
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return None


# --------------------------------------------------------------------------
# Global 401 formatting safeguard (ensures consistent payload shape)
# --------------------------------------------------------------------------

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    from fastapi.responses import JSONResponse

    headers = exc.headers or {}
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)