# NEXUS — Autonomous WebApp Generation Platform
## Comprehensive Architectural Design Document & Implementation Blueprint
**Document Version:** 1.0.0  
**Target Implementer:** Claude Code (Autonomous Implementation Engine)  
**Status:** Approved for Implementation  
**Date:** September 2026  

---

## 1. Executive Summary & Vision

### 1.1 Product Overview
**Nexus** is an enterprise-grade AI-powered web platform that empowers authenticated users to generate production-ready, full-stack web applications by simply uploading a standard `user_requirement.md` document. 

Nexus acts as an autonomous software factory:
1. **Intake & Parsing:** Authenticated users upload or edit their software requirement markdown (`user_requirement.md`).
2. **Agentic Orchestration:** The Nexus backend triggers a multi-agent AI pipeline (Team Lead / Architect, Frontend Engineer, Backend Engineer, QA Automation Tester).
3. **Real-Time Visibility:** The client provides a high-fidelity "Mission Control" dashboard that streams agent reasoning (`Thought`), tool execution (`ToolCall` / `ToolResult`), and code file generation events in real time.
4. **Self-Correction & Testing:** An automated QA agent verifies syntax, schema consistency, and end-to-end integration (via Playwright headless testing and sandbox linting) with iterative self-correction loops.
5. **Packaged Delivery:** The platform generates a validated, production-structured repository archive (`.zip`) containing full source code for both Frontend and Backend, environment configurations, and an automated startup runner script (`start_servers.sh`), downloadable directly from the web interface.

### 1.2 Target Audience & Usage Persona
- **Product Managers & Founders:** Rapidly prototype functional MVPs from specifications.
- **Developers & Engineers:** Scaffold complete boilerplate apps with models, routes, state management, and modern UI in minutes.
- **Enterprise Teams:** Standardize software scaffolding compliant with architectural specifications.

---

## 2. High-Level System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        USER BROWSER / CLIENT                           │
│  Nuxt 3 + Vue 3 + Tailwind CSS + Pinia + WebSocket / SSE Realtime Client│
└──────────────────┬─────────────────────────────────▲───────────────────┘
                   │ HTTPS (REST API)                │ WSS (Live Log Stream)
                   ▼                                 │
┌────────────────────────────────────────────────────┴───────────────────┐
│                    NEXUS BACKEND API GATEWAY                           │
│     Django 5.x + Django REST Framework + Django Channels + ASGI        │
│  - User Auth (JWT & Refresh)  - Project & Requirement Management       │
│  - REST API Viewsets          - WebSocket Consumer Channel Layer       │
└──────────┬─────────────────────────────┬───────────────────────────────┘
           │                             │
           ▼                             ▼
┌──────────────────────┐      ┌──────────────────────────────────────────┐
│   DATABASE & CACHE   │      │        ASYNCHRONOUS TASK BROKER          │
│ PostgreSQL 16+       │      │ Redis 7.x + Celery Workers / Task Runner │
│ (Users, Projects,    │      └────────────────────┬─────────────────────┘
│  Tasks, Agent Logs)  │                           │ Dispatches
└──────────────────────┘                           ▼
                              ┌──────────────────────────────────────────┐
                              │      AGENTIC AI PIPELINE WORKER          │
                              │  Google Antigravity SDK / Multi-Agent    │
                              │  Gemini 3.5 Flash Orchestration Engine  │
                              │                                          │
                              │  ┌────────────────────────────────────┐  │
                              │  │ Phase 1: Team Lead / Architect     │  │
                              │  │  - Analyzes user_requirement.md    │  │
                              │  │  - Generates DDS & File Manifest   │  │
                              │  └─────────────────┬──────────────────┘  │
                              │                    │                     │
                              │       ┌────────────┴───────────┐         │
                              │       ▼                        ▼         │
                              │  ┌──────────────┐     ┌───────────────┐  │
                              │  │ Frontend Dev │ ║   │  Backend Dev  │  │
                              │  │ Agent (Nuxt) │     │ Agent (Django)│  │
                              │  └────────┬─────┘     └───────┬───────┘  │
                              │           └───────────┬───────┘          │
                              │                       ▼                  │
                              │  ┌────────────────────────────────────┐  │
                              │  │ Phase 3: QA & Self-Correcting Loop │  │
                              │  │  - Syntax Check & Playwright E2E   │  │
                              │  │  - Feedback loop to Agents if fail │  │
                              │  └─────────────────┬──────────────────┘  │
                              │                    ▼                     │
                              │  ┌────────────────────────────────────┐  │
                              │  │ Phase 4: Packager & ZIP Bundler    │  │
                              │  │  - Validates manifests & zips      │  │
                              │  └─────────────────┬──────────────────┘  │
                              └────────────────────┼─────────────────────┘
                                                   │ Writes artifact
                                                   ▼
                              ┌──────────────────────────────────────────┐
                              │     SANDBOX FILE SYSTEM / STORAGE        │
                              │  /workspace/projects/{project_uuid}/     │
                              │  - generated/ (frontend + backend code)  │
                              │  - packages/project_{uuid}_complete.zip  │
                              └──────────────────────────────────────────┘
```

---

## 3. Technology Stack & Framework Selection

| Tier | Technology | Version | Purpose & Rationale |
|---|---|---|---|
| **Frontend Framework** | **Nuxt 3 / Vue 3** | `3.13+` | Server-Side Rendering (SSR) capable, file-based routing, auto-imports, high developer velocity, and seamless Vue 3 Composition API. |
| **Language (Frontend)** | **TypeScript** | `5.5+` | Strict type safety across API client responses and component props. |
| **Styling** | **Tailwind CSS + Tailwind Typography** | `3.4+` | Modern design system, fluid dark-mode palette, clean typography for markdown previews. |
| **Icons & UI** | **Lucide Vue Next + Radix Vue** | Latest | Accessible, modern component primitives and crisp iconography. |
| **Code & Markdown Viewer** | **Monaco Editor / Prism.js + Shiki** | Latest | High-fidelity syntax-highlighted code explorer for generated outputs and requirement preview. |
| **Backend Framework** | **Django + Django REST Framework (DRF)** | `5.1+` | Battle-tested security, robust ORM, built-in user management, clean serializer validation, and Django Channels support. |
| **Asynchronous Engine** | **Django Channels + Daphne / Uvicorn** | Latest | ASGI server supporting native WebSockets for streaming agent logs and terminal output. |
| **Task Queue & Broker** | **Celery + Redis** | Celery 5.4+ / Redis 7.2+ | Distributed, long-running agent pipeline execution without blocking HTTP request threads. |
| **Database** | **PostgreSQL** | `16+` | ACID transactional storage for user credentials, project metadata, step-by-step agent logs, and artifact indices. |
| **Agentic AI SDK** | **Google Antigravity SDK** (`google-antigravity`) | Latest | Multi-agent autonomous system, streaming `Thought`, `ToolCall`, and `ToolResult` chunks. |
| **AI Model** | **Gemini 3.5 Flash** (`gemini-3.5-flash`) | GA | High token-throughput, 1M context window, superior code generation, low latency, and robust tool-calling support. |
| **MCP Tool Servers** | **Model Context Protocol** | Verified Spec | File system operations (`@modelcontextprotocol/server-filesystem`), sequential planning (`@modelcontextprotocol/server-sequential-thinking`), and browser automation (`@playwright/mcp`). |
| **Archive & Packaging** | **Python `zipfile` + `shutil`** | Built-in | Fast streaming zip creation with automated exclusions (`node_modules`, `.venv`, `.git`). |

---

## 4. Complete Database Schema (PostgreSQL)

### 4.1 ER Diagram Overview
```
┌─────────────────┐       1:N       ┌────────────────────────┐
│     User        ├─────────────────┤        Project         │
│  (Custom User)  │                 │  (Name, Status, Slug)  │
└─────────────────┘                 └───────────┬────────────┘
                                                │
                       ┌────────────────────────┼────────────────────────┐
                   1:1 │                    1:N │                    1:1 │
                       ▼                        ▼                        ▼
         ┌─────────────────────────┐ ┌────────────────────┐ ┌───────────────────────┐
         │     RequirementDoc      │ │   GenerationTask   │ │   GeneratedArtifact   │
         │ (File path, raw md text)│ │ (Status, Timeline) │ │(Zip path, size, hash) │
         └─────────────────────────┘ └──────────┬─────────┘ └───────────────────────┘
                                                │
                                            1:N │
                                                ▼
                                     ┌────────────────────┐
                                     │   AgentStepLog     │
                                     │(Agent, Type, Chunk)│
                                     └────────────────────┘
```

### 4.2 Data Model Definitions (Django Models Specification)

#### A. Custom User Model (`accounts.models.User`)
```python
class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
```

#### B. Project Model (`projects.models.Project`)
```python
class ProjectStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    QUEUED = 'QUEUED', 'Queued'
    PLANNING = 'PLANNING', 'Planning & Architecture'
    GENERATING = 'GENERATING', 'Generating Code (FE & BE)'
    TESTING = 'TESTING', 'Testing & Self-Correction'
    PACKAGING = 'PACKAGING', 'Packaging Archive'
    COMPLETED = 'COMPLETED', 'Completed'
    FAILED = 'FAILED', 'Failed'

class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, blank=True)
    description = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=ProjectStatus.choices, default=ProjectStatus.DRAFT)
    error_message = models.TextField(blank=True, null=True)
    workspace_dir = models.CharField(max_length=500, blank=True)  # Isolated disk path
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

#### C. Requirement Document Model (`projects.models.RequirementDoc`)
```python
class RequirementDoc(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='requirement_doc')
    file = models.FileField(upload_to='requirements/%Y/%m/%d/')
    original_filename = models.CharField(max_length=255, default='user_requirement.md')
    raw_content = models.TextField(help_text="Extracted plain text of user_requirement.md")
    word_count = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

#### D. Generation Task Model (`projects.models.GenerationTask`)
```python
class GenerationTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='generation_tasks')
    celery_task_id = models.CharField(max_length=255, blank=True, null=True)
    current_phase = models.CharField(max_length=50, default='INITIALIZING')
    progress_percentage = models.PositiveSmallIntegerField(default=0)  # 0 to 100
    qa_iterations = models.PositiveSmallIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
```

#### E. Agent Step Log Model (`projects.models.AgentStepLog`)
```python
class LogType(models.TextChoices):
    THOUGHT = 'THOUGHT', 'Thought'
    TOOL_CALL = 'TOOL_CALL', 'Tool Call'
    TOOL_RESULT = 'TOOL_RESULT', 'Tool Result'
    TEXT = 'TEXT', 'Text Output'
    PHASE_CHANGE = 'PHASE_CHANGE', 'Phase Change'
    SYSTEM = 'SYSTEM', 'System Notification'
    ERROR = 'ERROR', 'Error'

class AgentStepLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    task = models.ForeignKey(GenerationTask, on_delete=models.CASCADE, related_name='logs')
    agent_name = models.CharField(max_length=100)  # 'Team Lead', 'Frontend Dev', 'Backend Dev', 'QA'
    log_type = models.CharField(max_length=20, choices=LogType.choices)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)  # Tool arguments, return codes, file paths
    sequence_num = models.PositiveIntegerField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

#### F. Generated Artifact Model (`projects.models.GeneratedArtifact`)
```python
class GeneratedArtifact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='artifact')
    zip_file = models.FileField(upload_to='artifacts/%Y/%m/%d/')
    file_name = models.CharField(max_length=255)
    file_size_bytes = models.BigIntegerField(default=0)
    sha256_checksum = models.CharField(max_length=64, blank=True)
    total_files_count = models.PositiveIntegerField(default=0)
    frontend_framework = models.CharField(max_length=50, default='Nuxt 3')
    backend_framework = models.CharField(max_length=50, default='Django 5')
    created_at = models.DateTimeField(auto_now_add=True)
```

---

## 5. REST & WebSocket API Specification

### 5.1 Authentication Endpoints (`/api/v1/auth/`)
All responses use standard JSON wrapping: `{ "success": true, "data": { ... } }` or `{ "success": false, "error": { "code": "...", "message": "..." } }`.

- `POST /api/v1/auth/register/`
  - **Payload:** `{ "email": "user@example.com", "password": "SecurePassword123!", "full_name": "Alex Taylor" }`
  - **Response 201:** `{ "success": true, "data": { "user": { "id": "uuid", "email": "user@example.com", "full_name": "Alex Taylor" }, "tokens": { "access": "...", "refresh": "..." } } }`
- `POST /api/v1/auth/login/`
  - **Payload:** `{ "email": "user@example.com", "password": "SecurePassword123!" }`
  - **Response 200:** Access and refresh JWT tokens.
- `POST /api/v1/auth/refresh/`
  - **Payload:** `{ "refresh": "..." }`
  - **Response 200:** New access token.
- `GET /api/v1/auth/me/`
  - **Headers:** `Authorization: Bearer <access_token>`
  - **Response 200:** User profile and usage quota summary.

### 5.2 Projects & Requirement Upload Endpoints (`/api/v1/projects/`)
All endpoints require Bearer JWT token in the `Authorization` header.

- `GET /api/v1/projects/`
  - **Response 200:** List of user's projects with status, timestamps, and download readiness.
- `POST /api/v1/projects/`
  - **Payload:** `{ "name": "Inventory SaaS App", "description": "Multi-tenant inventory tracker" }`
  - **Response 201:** Created project record.
- `GET /api/v1/projects/{project_id}/`
  - **Response 200:** Project details, status, requirement preview, and latest generation task.
- `POST /api/v1/projects/{project_id}/requirement/`
  - **Content-Type:** `multipart/form-data`
  - **Form Fields:** `file`: `user_requirement.md` (Max size: 5 MB) OR raw text in `content` field.
  - **Validation:** Must be markdown format (`.md`), cannot be empty, must contain at least 20 words.
  - **Response 200:** Requirement saved, parsed word count returned.
- `POST /api/v1/projects/{project_id}/generate/`
  - **Payload:** `{ "force_restart": false }`
  - **Logic:** Validates that `RequirementDoc` exists. Enqueues a Celery job. Sets status to `QUEUED`.
  - **Response 202:** `{ "success": true, "data": { "task_id": "uuid", "status": "QUEUED" } }`
- `GET /api/v1/projects/{project_id}/files/`
  - **Response 200:** Tree structure of generated files (path, size, extension) for in-browser inspection.
- `GET /api/v1/projects/{project_id}/files/content/?path=frontend/app.vue`
  - **Response 200:** Plaintext content of requested file for live syntax-highlighted code preview.
- `GET /api/v1/projects/{project_id}/download/`
  - **Response 200:** Streams the generated `.zip` archive as `application/zip` with `Content-Disposition: attachment; filename="nexus_project_{name}.zip"`.

### 5.3 WebSocket Real-Time Log Streaming
- **Endpoint:** `ws://localhost:8000/ws/projects/{project_id}/logs/?token=<jwt_access_token>`
- **Protocol:**
  - Upon connection, server sends historical logs of the current task.
  - During pipeline execution, server broadcasts real-time events.

```json
// Event Format
{
  "type": "log_event",
  "data": {
    "task_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "agent_name": "Team Lead",
    "log_type": "THOUGHT",
    "content": "Analyzing user_requirement.md. Identified 4 data entities and 6 API endpoints.",
    "sequence_num": 14,
    "timestamp": "2026-09-25T08:15:30.123Z"
  }
}
```

```json
// Progress & Phase Update Format
{
  "type": "phase_update",
  "data": {
    "current_phase": "GENERATING",
    "progress_percentage": 45,
    "active_agents": ["Frontend Dev", "Backend Dev"],
    "files_created_count": 18
  }
}
```

---

## 6. Multi-Agent AI Pipeline (The Core Engine)

### 6.1 Agent Roles & Architecture Flow

```
                      ┌──────────────────────┐
                      │ user_requirement.md  │
                      └──────────┬───────────┘
                                 │
                                 ▼
                      ┌──────────────────────┐
                      │ Phase 1: Team Lead   │
                      │  (System Architect)  │
                      └──────────┬───────────┘
                                 │ Generates:
                                 │ - .agents/dds_output.md (Design Doc Spec)
                                 │ - .agents/manifest.json (File roadmap)
                                 │
                     ┌───────────┴───────────┐
                     │ Parallel Execution    │
                     ▼                       ▼
            ┌─────────────────┐     ┌─────────────────┐
            │ Phase 2A:       │     │ Phase 2B:       │
            │ Frontend Dev    │     │ Backend Dev     │
            │ (Nuxt 3 / Vue3) │     │ (Django 5 / DRF)│
            └────────┬────────┘     └────────┬────────┘
                     │                       │
                     │ Writes: ./frontend/*  │ Writes: ./backend/*
                     │ Saves: fe_output.md   │ Saves: be_output.md
                     └───────────┬───────────┘
                                 │
                                 ▼
            ┌─────────────────────────────────────────┐
            │ Phase 3: QA & Self-Correcting Loop      │
            │  1. Check files against manifest        │
            │  2. Execute linting & build syntax check│
            │  3. Spin up temp test servers           │
            │  4. Run Playwright E2E verification     │
            └────────────────────┬────────────────────┘
                                 │
                   ┌─────────────┴─────────────┐
                   │ Pass / Fail Decision      │
                   ▼                           ▼
            [❌ Tests Failed]           [✅ Tests Passed]
                   │                           │
          Iterate (Max 3 loops):               ▼
          - QA passes error report      ┌──────────────────────┐
            back to Team Lead           │ Phase 4: Bundler     │
          - Team Lead patches DDS       │ - Creates startup sh │
          - FE / BE apply surgical fix  │ - Generates README   │
          - QA re-validates             │ - Compresses to .zip │
                                        └──────────────────────┘
```

### 6.2 Agent Specifications & Tools

#### 1. Team Lead Agent (Architect & Orchestrator)
- **Role:** Deconstructs `user_requirement.md` into functional modules, database schemas, REST endpoints, UI component hierarchy, and file path manifests.
- **Model:** `gemini-3.5-flash`
- **MCP Servers:**
  - `name="thinking"`: `@modelcontextprotocol/server-sequential-thinking`
  - `name="filesystem"`: `@modelcontextprotocol/server-filesystem` targeting `./`
- **Output Artifact:** `.agents/dds_output.md` and `.agents/manifest.json`.

#### 2. Frontend Developer Agent
- **Role:** Implements the complete client-side Nuxt 3 application matching the DDS specification.
- **Rules:**
  - Uses Vue 3 `<script setup lang="ts">`.
  - Uses Tailwind CSS classes with modern aesthetics, clean margins, and dark mode support.
  - Implements API interaction via `useFetch` or `$fetch` configured with dynamic base URL (`http://localhost:8000`).
  - Creates responsive layouts, navigation bars, state stores (Pinia), and route pages.
- **MCP Servers:**
  - `name="filesystem-frontend"`: `@modelcontextprotocol/server-filesystem` targeting `./frontend`
- **Output Artifact:** Fully populated `./frontend` directory.

#### 3. Backend Developer Agent
- **Role:** Implements the complete Django REST Framework backend matching the DDS specification.
- **Rules:**
  - Configures PostgreSQL database connection using the macOS-compatible Unix socket pattern (`host='/tmp'`, `port='5432'`) and environment variable fallbacks.
  - Implements models with proper fields, indexes, and migrations (`makemigrations`).
  - Implements serializers, API views, permissions, and CORS headers (`django-cors-headers` allowing `http://localhost:3000`).
  - Sets up root `urls.py` with clean routing.
- **MCP Servers:**
  - `name="filesystem-backend"`: `@modelcontextprotocol/server-filesystem` targeting `./backend`
- **Output Artifact:** Fully populated `./backend` directory.

#### 4. QA Automation Tester Agent
- **Role:** Performs sanity audits, executes migrations, starts background test servers, runs static linting, and validates API health and browser rendering.
- **MCP Servers:**
  - `name="playwright"`: `@playwright/mcp`
  - `name="filesystem"`: `@modelcontextprotocol/server-filesystem` targeting `./`
- **Output Artifact:** `.agents/qa_report.md` with explicit status `PASS` or `FAIL` + detailed error stack traces.

### 6.3 Self-Correction Loop Algorithm
```python
# Self-Correction Engine in pipeline_orchestrator.py
MAX_QA_ITERATIONS = 3

for iteration in range(1, MAX_QA_ITERATIONS + 1):
    broadcast_log("QA", f"Starting QA Verification Loop {iteration}/{MAX_QA_ITERATIONS}")
    qa_report = await run_qa_agent(iteration)
    
    if "STATUS: PASS" in qa_report:
        broadcast_log("QA", "✅ All integration checks passed!")
        break
    else:
        if iteration == MAX_QA_ITERATIONS:
            raise GenerationPipelineError(f"QA verification failed after {MAX_QA_ITERATIONS} self-correction attempts.")
        
        broadcast_log("Team Lead", f"⚠️ QA Failure detected. Initiating repair cycle {iteration}...")
        repair_plan = await run_team_lead_repair_agent(qa_report)
        
        # Parallel surgical fixes
        await asyncio.gather(
            run_frontend_repair_agent(repair_plan),
            run_backend_repair_agent(repair_plan)
        )
```

### 6.4 Rate Limiting & Robustness Patterns
Following proven Google Antigravity SDK operational rules:
1. **Pydantic Name Validation:** Every `types.McpStdioServer` must have a non-empty alphanumeric `name` (e.g., `name="filesystem-fe"`).
2. **Fresh Agent Per Attempt:** On HTTP `429` / `503` / `RESOURCE_EXHAUSTED` or `ConnectionClosedOK`, never reuse the closed WebSocket `Agent` instance. Instantiate a fresh `Agent(config_fn())` and apply exponential backoff (at least 70 seconds to reset quota windows).
3. **Verbose Streaming Mode:** The worker streams every `Thought`, `ToolCall`, `ToolResult`, and token directly to Redis Pub/Sub, which relays it through Django Channels to the user's browser.

---

## 7. Frontend User Experience & UI/UX Design

### 7.1 Visual Aesthetic Standards
- **Color Palette:** Deep obsidian dark mode (`bg-slate-950`, `bg-slate-900`, `border-slate-800`), with electric indigo (`#6366f1`) and cyan (`#06b6d4`) accent gradients.
- **Card Styling:** Translucent glassmorphism (`backdrop-blur-md bg-slate-900/60 border border-slate-800/80 shadow-2xl`).
- **Typography:** Inter or Outfit font family, with crisp contrast and syntax-colored badge indicators for status.

### 7.2 Core Screens & Layouts

#### Screen 1: Authentication (`/auth/login` and `/auth/register`)
- Clean split-screen design: Left side showcases Nexus feature highlights and animated agent workflow graphic; Right side contains the auth card with validation and error alerts.

#### Screen 2: Dashboard (`/dashboard`)
- **Header:** User profile, quota meter, and prominent **"+ New WebApp Project"** button.
- **Projects Grid:** Cards displaying project name, status badge (`Draft`, `Building`, `Ready for Download`), creation date, and quick action buttons (Open Mission Control, Download Zip, Delete).

#### Screen 3: Project Requirement Intake (`/projects/[id]`)
- **Dual Intake Modes:**
  - **Upload Tab:** Drag-and-drop zone accepting `user_requirement.md` with instant file validation and size check.
  - **Editor Tab:** In-browser markdown editor with split preview and preset templates ("E-Commerce Store", "SaaS Dashboard", "Social Feed", "Custom").
- **Action Bar:** "Save Draft" and a glowing "Start Autonomous Generation" button.

#### Screen 4: Mission Control & Live Generation (`/projects/[id]/generate`)
- **Top Pipeline Tracker:** Interactive horizontal stepper:
  `[1. Requirement Analysis] -> [2. Architecture Design] -> [3. Parallel Coding] -> [4. QA Self-Correction] -> [5. Packaged]`
- **Live Terminal & Agent Stream:**
  - Filter tabs: `All`, `Team Lead`, `Frontend`, `Backend`, `QA Tester`.
  - Stream display with animated indicator icons:
    - 🧠 `Thought`: Agent internal reasoning shown in muted purple.
    - 🔧 `Tool Call`: File operations, bash commands, or MCP tools in cyan.
    - ✅ `Tool Result`: Tool execution outcome with collapsible detail.
    - ⚡ `Status`: Current file being written.
- **Real-Time File Tree:** Sidebar showing files appearing dynamically as agents create them (`frontend/pages/index.vue`, `backend/apps/core/models.py`, etc.).

#### Screen 5: Delivery & Download Hub (`/projects/[id]/ready`)
- **Completion Banner:** Celebration animation showing project statistics (Total lines of code, number of files, QA passes, generation duration).
- **Code Explorer:** Split-view interactive tree explorer and syntax-highlighted viewer (powered by Monaco/Shiki) to inspect the generated code directly in the browser.
- **Quick-Start Instructions:** Rendered preview of the generated `README.md` and copy-paste terminal command (`./scripts/start_servers.sh`).
- **Download Action:** Large, prominent **"Download Complete Source Code (.ZIP)"** button with size indicator.

---

## 8. Directory & File Manifest of the Nexus Project

The following tree represents the complete codebase to be implemented:

```
New_Nexus_Web/
├── .env.example
├── .gitignore
├── README.md
├── docker-compose.yml
├── scripts/
│   ├── setup_environment.sh          # Installs dependencies, sets up PostgreSQL & Redis
│   ├── start_dev.sh                  # Concurrently launches Daphne (Backend) and Nuxt (Frontend)
│   └── test_agent_pipeline.sh        # Standalone verification script for agent pipeline
│
├── backend/                          # Django 5 + DRF + Channels Service
│   ├── manage.py
│   ├── requirements.txt
│   ├── nexus_backend/
│   │   ├── __init__.py
│   │   ├── asgi.py                  # ASGI configuration with ProtocolTypeRouter & Channel auth
│   │   ├── wsgi.py
│   │   ├── settings.py              # Settings with JWT, CORS, Channels, Celery, and DB config
│   │   └── urls.py                  # Master URL routing
│   ├── apps/
│   │   ├── accounts/                # Custom User, Auth Views, JWT Serializers
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   └── urls.py
│   │   ├── projects/                # Project CRUD, Requirement upload, Artifact download
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   └── urls.py
│   │   └── realtime/                # Django Channels WebSocket Consumers
│   │       ├── __init__.py
│   │       ├── consumers.py         # ProjectLogConsumer (WebSocket relay)
│   │       └── routing.py
│   └── engine/                      # Autonomous Multi-Agent Core Engine
│       ├── __init__.py
│       ├── celery_app.py            # Celery broker configuration
│       ├── tasks.py                 # Celery entrypoint for run_generation_task
│       ├── orchestrator.py          # Coordinates 4 agents, self-correction loop, rate-limits
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── architect.py         # Team Lead agent configuration and prompt
│       │   ├── frontend_dev.py      # Frontend developer agent configuration
│       │   ├── backend_dev.py       # Backend developer agent configuration
│       │   └── qa_tester.py         # QA tester agent configuration
│       ├── mcp/
│       │   └── registry.py          # Verified MCP server configurations with name= kwargs
│       └── packager/
│           ├── __init__.py
│           ├── generator.py         # Adds start_servers.sh, README.md, and .env
│           └── zipper.py            # Creates clean .zip archive and generates SHA256
│
└── frontend/                         # Nuxt 3 Client Application
    ├── package.json
    ├── tsconfig.json
    ├── nuxt.config.ts
    ├── tailwind.config.js
    ├── app.vue                      # Root layout wrapper with toast notifications
    ├── assets/
    │   └── css/
    │       └── main.css             # Tailwind base styles and dark theme overrides
    ├── composables/
    │   ├── useAuth.ts               # JWT auth state, login, register, logout, token refresh
    │   ├── useProjects.ts           # Project CRUD API operations
    │   └── useProjectSocket.ts      # WebSocket connection manager for live streaming logs
    ├── components/
    │   ├── ui/                      # Buttons, Badges, Modals, Inputs, Loaders
    │   │   ├── BaseButton.vue
    │   │   ├── BaseInput.vue
    │   │   └── StatusBadge.vue
    │   ├── dashboard/
    │   │   ├── ProjectCard.vue
    │   │   └── CreateProjectModal.vue
    │   ├── requirement/
    │   │   ├── FileUploadZone.vue   # Drag-and-drop user_requirement.md
    │   │   └── MarkdownEditor.vue   # Monaco / Shiki markdown editor preview
    │   ├── generation/
    │   │   ├── PipelineStepper.vue  # Horizontal phase progression tracker
    │   │   ├── TerminalStream.vue   # Live agent thought and tool call viewer
    │   │   └── FileTreePreview.vue  # Real-time generated files tree
    │   └── delivery/
    │       ├── CodeViewer.vue       # Syntax highlighted code explorer
    │       └── DownloadCard.vue     # Archive details and 1-click download button
    ├── layouts/
    │   ├── default.vue              # Main authenticated app layout (Header, Nav, Container)
    │   └── auth.vue                 # Minimal auth layout
    ├── middleware/
    │   └── auth.ts                  # Route navigation guard (redirects if unauthenticated)
    └── pages/
        ├── index.vue                # Marketing / Landing redirect
        ├── auth/
        │   ├── login.vue
        │   └── register.vue
        ├── dashboard/
        │   └── index.vue            # Projects list overview
        └── projects/
            ├── [id]/
            │   ├── index.vue        # Requirement upload & preview page
            │   ├── mission-control.vue # Live generation streaming cockpit
            │   └── ready.vue        # Completed project inspection & download hub
```

---

## 9. Detailed Generated App Output Specification

When Nexus completes the generation of a user's web application, the generated directory structure packaged into the final `.zip` must adhere to this standardized architecture:

```
[project_slug]_generated/
├── README.md                        # Complete project setup and deployment documentation
├── start_servers.sh                 # One-click startup script (starts DB, backend, frontend)
├── .env.example
├── backend/                         # Generated Django REST API
│   ├── manage.py
│   ├── requirements.txt
│   ├── [app_name]_backend/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   └── api/
│       ├── models.py
│       ├── serializers.py
│       ├── views.py
│       └── urls.py
└── frontend/                        # Generated Nuxt 3 Client
    ├── package.json
    ├── nuxt.config.ts
    ├── tailwind.config.js
    ├── app.vue
    ├── pages/
    └── components/
```

### Standardized Generated `start_servers.sh` Script
Nexus must bundle a robust startup script into the `.zip` archive:
```bash
#!/usr/bin/env bash
set -e

echo "=========================================="
echo " Starting Your Generated WebApp "
echo "=========================================="

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. Setup Backend
echo "--> Setting up Python Virtual Environment..."
cd "$PROJECT_ROOT/backend"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate --fake-initial || python manage.py migrate

# 2. Setup Frontend
echo "--> Setting up Frontend Dependencies..."
cd "$PROJECT_ROOT/frontend"
npm install --cache /tmp/npm-cache-$(basename "$PROJECT_ROOT")

# 3. Launch Services Concurrently
echo "--> Starting Backend on http://localhost:8000..."
cd "$PROJECT_ROOT/backend"
.venv/bin/python manage.py runserver 8000 &
BACKEND_PID=$!

echo "--> Starting Frontend on http://localhost:3000..."
cd "$PROJECT_ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

cleanup() {
    echo "Shutting down servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "Application is ready!"
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000"
wait
```

---

## 10. Security, Sandboxing & Storage Design

### 10.1 Authentication & Security Controls
1. **Password Hashing:** Argon2 / PBKDF2 with SHA-256 via Django's authentication system.
2. **JWT Security:** Short-lived access tokens (15 minutes), refresh tokens (7 days) with rotation and blacklist support (`djangorestframework-simplejwt`).
3. **CORS Hardening:** Configured whitelist permitting only `http://localhost:3000` (or dynamic deployment domain).
4. **Requirement File Sanitization:**
   - Strict size limit of 5 MB per `user_requirement.md`.
   - MIME validation and extension checks to prevent executable script uploads.
   - Text decoding with replacement of non-UTF8 characters.

### 10.2 File System Sandboxing
To ensure tenant isolation and prevent malicious file overwrites:
1. Each project generation executes in an isolated workspace path:
   `MEDIA_ROOT/workspaces/{user_id}/{project_id}/`
2. All MCP file system servers (`@modelcontextprotocol/server-filesystem`) are explicitly constrained to this directory path as their root.
3. The QA agent executes commands in this scoped working directory.

---

## 11. Claude Code Step-by-Step Implementation Roadmap

This section defines the precise sequential implementation order that **Claude Code** must follow to build the entire Nexus system from scratch.

### Phase 1: Environment & Project Scaffolding
- **Goal:** Set up workspace root, virtual environment, and directory structures.
- **Tasks:**
  1. Create top-level directories: `backend/`, `frontend/`, `scripts/`, `media/`, `static/`.
  2. Create Python virtual environment `.venv` and install:
     `django djangorestframework djangorestframework-simplejwt django-cors-headers channels daphne celery redis psycopg2-binary python-dotenv google-antigravity`.
  3. Initialize Django project `nexus_backend` in `backend/` and apps: `accounts`, `projects`, `realtime`.
  4. Initialize Nuxt 3 project in `frontend/` with Tailwind CSS, Lucide icons, Pinia, and TypeScript.
  5. Create `scripts/setup_environment.sh` and `.env.example`.

### Phase 2: Backend Core, Models & Database Migrations
- **Goal:** Implement persistent data storage and authentication.
- **Tasks:**
  1. Implement Custom User model with email authentication in `apps/accounts/models.py`.
  2. Implement `Project`, `RequirementDoc`, `GenerationTask`, `AgentStepLog`, and `GeneratedArtifact` models in `apps/projects/models.py`.
  3. Configure PostgreSQL connection with fallback to SQLite for immediate local testing.
  4. Run `makemigrations` and `migrate`.
  5. Implement JWT login, register, and profile endpoints in `apps/accounts/`.

### Phase 3: Project CRUD & Requirement Upload API
- **Goal:** Allow users to create projects and upload their markdown requirements.
- **Tasks:**
  1. Implement `ProjectViewSet` supporting `list`, `create`, `retrieve`, `destroy`.
  2. Implement requirement upload action `POST /api/v1/projects/{id}/requirement/` supporting both multipart file upload and raw content text.
  3. Implement file preview endpoint `GET /api/v1/projects/{id}/files/` and file content endpoint.
  4. Implement artifact download endpoint `GET /api/v1/projects/{id}/download/`.

### Phase 4: Autonomous Multi-Agent AI Pipeline
- **Goal:** Build the Antigravity multi-agent code generator.
- **Tasks:**
  1. Implement `engine/mcp/registry.py` configuring verified MCP servers (`server-sequential-thinking`, `server-filesystem`, `@playwright/mcp`) ensuring every server has `name=`.
  2. Implement agent prompts in `engine/agents/`:
     - `architect.py` (Deconstructs `user_requirement.md` into DDS and file manifest).
     - `frontend_dev.py` (Generates Nuxt 3 frontend application).
     - `backend_dev.py` (Generates Django REST API application).
     - `qa_tester.py` (Validates code, runs tests, checks manifests).
  3. Implement `engine/orchestrator.py`:
     - Execution sequence with parallel FE & BE phases.
     - Self-correction loop with max 3 iterations on QA failure.
     - Rate-limit handling with fresh `Agent()` instances and 70-second backoff.
     - Real-time streaming generator capturing `Thought`, `ToolCall`, `ToolResult`, and `Text`.
  4. Implement `engine/packager/zipper.py`:
     - Injects `start_servers.sh` and comprehensive `README.md`.
     - Compresses generated project into `project_{uuid}_complete.zip`.
  5. Connect Celery task in `engine/tasks.py` to trigger the orchestrator.

### Phase 5: Real-Time WebSocket Streaming
- **Goal:** Stream live agent activity to the browser.
- **Tasks:**
  1. Implement `apps/realtime/consumers.py` (`ProjectLogConsumer`) with channel groups based on `project_id`.
  2. Configure `asgi.py` with `ProtocolTypeRouter` and `URLRouter`.
  3. Wire the orchestrator's log broadcaster to send events to the channel group.

### Phase 6: Frontend Implementation
- **Goal:** Build the complete Nuxt 3 client UI.
- **Tasks:**
  1. Set up Pinia stores and composables: `useAuth.ts`, `useProjects.ts`, `useProjectSocket.ts`.
  2. Build authentication pages: `pages/auth/login.vue`, `pages/auth/register.vue`.
  3. Build Dashboard: `pages/dashboard/index.vue` with project cards and project creation modal.
  4. Build Requirement Intake: `pages/projects/[id]/index.vue` with file drag-and-drop and markdown editor.
  5. Build Mission Control: `pages/projects/[id]/mission-control.vue` with horizontal stepper, live log stream, agent tabs, and real-time file tree.
  6. Build Delivery Hub: `pages/projects/[id]/ready.vue` with code viewer and 1-click zip download.

### Phase 7: Verification & Acceptance Testing
- **Goal:** Validate end-to-end user workflow.
- **Verification Script:**
  1. Create a dummy test user and log in.
  2. Create a project and upload a test `user_requirement.md` (e.g., Simple Todo List WebApp).
  3. Trigger generation and verify:
     - WebSocket connects and streams `Thought` and `ToolCall` events.
     - Files are created under `./media/workspaces/...`.
     - QA phase passes.
     - `.zip` artifact is created and downloadable.
     - Unzipping the archive and running `./start_servers.sh` spins up both frontend and backend without syntax or migration errors.

---

## 12. Verification & Acceptance Criteria Checklist

For Claude Code to declare implementation complete, all the following checkpoints must pass:

- [ ] **Auth Flow:** User can register with email/password, log in, receive JWT tokens, and access protected routes. Unauthenticated users are redirected to `/auth/login`.
- [ ] **Upload Handling:** `user_requirement.md` can be uploaded via drag-and-drop or typed in the web editor, and is persisted to the database.
- [ ] **Agent Execution:** Calling `POST /api/v1/projects/{id}/generate/` successfully triggers the multi-agent worker.
- [ ] **Streaming Logs:** The Mission Control interface displays live streaming thought chunks, tool calls, and phase progress bars in real time without refreshing.
- [ ] **Generated App Completeness:** The output directory contains both functional `./frontend/` (Nuxt 3) and `./backend/` (Django 5) matching the user's specification.
- [ ] **Self-Correction:** If an intentional syntax error or missing model field is injected during testing, the QA tester detects it, triggers the repair cycle, and successfully fixes the issue.
- [ ] **Download:** The user can click "Download Complete Source Code" and receives a valid `.zip` containing all code, `.env.example`, and an executable `start_servers.sh`.
- [ ] **Clean Startup:** The extracted generated webapp runs cleanly with `./start_servers.sh` on macOS/Linux.
