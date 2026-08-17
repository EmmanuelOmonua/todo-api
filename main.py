import os
import sys
import json
import uuid
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from datetime import timedelta

import psycopg
import asyncio
from psycopg.rows import dict_row
from fastapi import FastAPI, status, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, EmailStr, ValidationError, field_validator
from dotenv import load_dotenv
from supabase import create_client, Client
import jwt
from jwt.exceptions import PyJWTError
from openai import APITimeoutError, APIStatusError

# --- INNGEST IMPORTS ---
import inngest
import inngest.fast_api

from src.llm.schema import EnrichRequest, EnrichResponse, CategoryEnum
from src.llm.client import call_llm_raw, call_llm_repair
from src.llm.parser import parse_and_validate
from src.llm.quarantine import quarantine_payload
from src.llm.logger import log_llm_call

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

# LLM Control Flags
LLM_STUB = os.getenv("LLM_STUB", "1") == "1"

if not DATABASE_URL or not SUPABASE_URL or not SUPABASE_KEY or not SUPABASE_JWT_SECRET:
    print("FATAL ERROR: Missing required environment variables.", file=sys.stderr)
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
security = HTTPBearer()

# --- IN-MEMORY REPORT STORE ---
reports_db: Dict[str, Dict[str, Any]] = {}


# --- SCHEMAS ---
class ReportCreateRequest(BaseModel):
    topic: str = Field(..., min_length=1)

    @field_validator("topic")
    @classmethod
    def validate_topic_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Topic cannot be empty or whitespace.")
        return v.strip()

class ReportResponse(BaseModel):
    id: str
    status: str
    topic: str
    result: Optional[Dict[str, Any]] = None

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1)

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    done: Optional[bool] = None

class UserAuth(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


# --- INNGEST CLIENT SETUP ---
inngest_client = inngest.Inngest(app_id="report-api")


# --- INNGEST FUNCTIONS ---
@inngest_client.create_function(
    fn_id="say-hello",
    trigger=inngest.TriggerEvent(event="test/hello"),
)
async def say_hello(ctx: inngest.Context):
    await ctx.step.sleep("wait-a-bit", timedelta(seconds=5))
    return "Hello from the background!"


@inngest_client.create_function(
    fn_id="make-report",
    trigger=inngest.TriggerEvent(event="report/requested"),
    retries=2,
)
async def make_report(ctx: inngest.Context):
    report_id = ctx.event.data.get("report_id")
    topic = ctx.event.data.get("topic", "General")

    # Stage 3 requirement: Simulate failure to test retries and backoff
    if topic and topic.strip().lower() == "fail":
        raise RuntimeError(f"Simulated background job failure for topic: '{topic}'")

    # Step 1: Stand-in for slow task (8s sleep)
    await ctx.step.sleep("do-the-slow-work", timedelta(seconds=8))

    # Step 2: Build report and update map status to "done"
    async def build_report():
        if report_id in reports_db:
            reports_db[report_id]["status"] = "done"
            reports_db[report_id]["result"] = {
                "summary": f"Completed automated analysis for topic: '{topic}'.",
                "insights": ["Key metric A looks stable", "Key metric B increased by 14%"],
                "generated_at": "2026-08-17"
            }
    await ctx.step.run("build-report", build_report)

    return {"status": "done", "report_id": report_id}


# --- REUSABLE AUTH DEPENDENCY (MIDDLEWARE) ---
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            options={"verify_signature": False, "verify_aud": True},
            audience="authenticated",
            algorithms=["ES256", "HS256"]
        )
        return payload
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

# --- AUTHORIZATION DEPENDENCY (403 FORBIDDEN GUARD) ---
def require_admin(user: dict = Depends(get_current_user)) -> dict:
    user_metadata = user.get("user_metadata", {})
    app_metadata = user.get("app_metadata", {})
    
    role = user_metadata.get("role") or app_metadata.get("role") or user.get("role")

    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin access required."
        )
    return user

def get_db_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=2)

def init_db():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        id SERIAL PRIMARY KEY,
                        title TEXT NOT NULL,
                        done BOOLEAN NOT NULL DEFAULT FALSE,
                        user_id VARCHAR(255)
                    );
                """)
                cur.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS user_id VARCHAR(255);")
            conn.commit()
    except psycopg.OperationalError as e:
        print(f"Database initialization failed: {e}", file=sys.stderr)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(init_db)
    yield

app = FastAPI(
    title="Todo API with Supabase Auth & LLM Enrichment",
    description="Interactive REST API built with FastAPI, PostgreSQL, Supabase JWT auth, and Ollama LLM.",
    version="1.0.0",
    lifespan=lifespan
)

# --- SERVE INNGEST AT /api/inngest ---
inngest.fast_api.serve(
    app,
    inngest_client,
    [say_hello, make_report],
)

@app.exception_handler(psycopg.OperationalError)
async def db_exception_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Database connection failed."}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "Invalid input payload standard validation error"}
    )

@app.get("/")
def read_root():
    return {"name": "Task API", "version": "1.0"}

# --- STAGE 0 HEALTH CHECK ROUTE ---
@app.get("/health")
def health_check():
    return {"status": "ok"}


# --- REPORT ENDPOINTS (STAGE 2 & STAGE 3) ---
@app.post("/reports", status_code=status.HTTP_202_ACCEPTED, response_model=ReportResponse)
async def create_report(payload: ReportCreateRequest):
    report_id = str(uuid.uuid4())
    
    # Store initial pending state
    reports_db[report_id] = {
        "id": report_id,
        "topic": payload.topic,
        "status": "pending",
        "result": None
    }

    # Dispatch background event
    await inngest_client.send(
        inngest.Event(
            name="report/requested",
            data={"report_id": report_id, "topic": payload.topic}
        )
    )

    return reports_db[report_id]


@app.get("/reports/{report_id}", response_model=ReportResponse)
def get_report_status(report_id: str):
    if report_id not in reports_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID '{report_id}' not found."
        )
    return reports_db[report_id]


# --- LLM ENRICHMENT ROUTE ---
@app.post("/enrich", response_model=EnrichResponse)
def enrich_content(payload: EnrichRequest):
    llm_enabled = os.getenv("LLM_ENABLED", "true").lower() in ("true", "1")
    if not llm_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM enrichment service is currently disabled."
        )

    stub_mode = os.getenv("LLM_STUB", "1") == "1"
    if stub_mode:
        return EnrichResponse(
            category=CategoryEnum.TECH,
            summary="This is a stubbed summary of the scraped content.",
            quality_flags=["stub_data"],
            confidence=0.95
        )

    try:
        raw_output, metrics = call_llm_raw(payload.content)
        
        try:
            response_obj = parse_and_validate(raw_output)
            log_llm_call(metrics, repaired=False, success=True)
            return response_obj
        except (json.JSONDecodeError, Exception) as err1:
            error_details = str(err1)

        repair_output, repair_metrics = call_llm_repair(payload.content, raw_output, error_details)
        try:
            response_obj = parse_and_validate(repair_output)
            log_llm_call(repair_metrics, repaired=True, success=True)
            return response_obj
        except (json.JSONDecodeError, Exception) as err2:
            log_llm_call(repair_metrics, repaired=True, success=False)
            quarantine_payload(
                content=payload.content,
                raw_output=raw_output,
                repair_output=repair_output,
                error_msg=str(err2)
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Model output failed validation after repair retry. Recorded to quarantine."
            )

    except APITimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LLM provider request timed out (30s limit)."
        )
    except APIStatusError as e:
        raise HTTPException(
            status_code=e.status_code if e.status_code in (401, 403, 400) else status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM Provider error: {e.message}"
        )

# --- PROTECTED PROFILE ROUTE ---
@app.get("/protected/profile")
def get_profile(user: dict = Depends(get_current_user)):
    return {
        "id": user.get("sub"),
        "email": user.get("email"),
        "created_at": user.get("iat")
    }

# --- ADMIN ROUTE (RBAC) ---
@app.get("/admin/users", status_code=status.HTTP_200_OK)
def list_admin_users(admin: dict = Depends(require_admin)):
    return {
        "message": "Welcome to the admin dashboard!",
        "admin_id": admin.get("sub"),
        "system_status": "All systems operational"
    }

# --- PROTECTED TASK ROUTES ---
@app.get("/tasks")
def get_tasks(user: dict = Depends(get_current_user)):
    user_id = user.get("sub")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, done FROM tasks WHERE user_id = %s ORDER BY id ASC;", (user_id,))
            return [{"id": row["id"], "title": row["title"], "done": row["done"]} for row in cur.fetchall()]

@app.get("/tasks/{task_id}")
def get_task(task_id: int, user: dict = Depends(get_current_user)):
    user_id = user.get("sub")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, done FROM tasks WHERE id = %s AND user_id = %s;", (task_id, user_id))
            row = cur.fetchone()
            if row is None:
                return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": f"Task {task_id} not found"})
            return row

@app.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(task_input: TaskCreate, user: dict = Depends(get_current_user)):
    user_id = user.get("sub")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tasks (title, done, user_id) VALUES (%s, %s, %s) RETURNING id;", (task_input.title, False, user_id))
            new_id = cur.fetchone()["id"]
        conn.commit()
    return {"id": new_id, "title": task_input.title, "done": False}

@app.put("/tasks/{task_id}")
def update_task(task_id: int, task_input: TaskUpdate, user: dict = Depends(get_current_user)):
    user_id = user.get("sub")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, done FROM tasks WHERE id = %s AND user_id = %s;", (task_id, user_id))
            row = cur.fetchone()
            if row is None:
                return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": f"Task {task_id} not found"})
            title = task_input.title if task_input.title is not None else row["title"]
            done = task_input.done if task_input.done is not None else row["done"]
            cur.execute("UPDATE tasks SET title = %s, done = %s WHERE id = %s AND user_id = %s;", (title, done, task_id, user_id))
        conn.commit()
    return {"id": task_id, "title": title, "done": done}

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, user: dict = Depends(get_current_user)):
    user_id = user.get("sub")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM tasks WHERE id = %s AND user_id = %s;", (task_id, user_id))
            if cur.fetchone() is None:
                return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": f"Task {task_id} not found"})
            cur.execute("DELETE FROM tasks WHERE id = %s AND user_id = %s;", (task_id, user_id))
        conn.commit()

# --- AUTH ROUTES ---
@app.post("/auth/signup", status_code=status.HTTP_201_CREATED)
def signup(credentials: UserAuth):
    try:
        response = supabase.auth.sign_up({"email": credentials.email, "password": credentials.password})
        if not response.user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Signup failed")
        return {"message": "User registered successfully", "user_id": response.user.id, "email": response.user.email}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.post("/auth/login")
def login(credentials: UserAuth):
    try:
        response = supabase.auth.sign_in_with_password({"email": credentials.email, "password": credentials.password})
        if not response.session:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        return {"access_token": response.session.access_token, "refresh_token": response.session.refresh_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user: dict = Depends(get_current_user)):
    try:
        supabase.auth.sign_out()
        return None
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))