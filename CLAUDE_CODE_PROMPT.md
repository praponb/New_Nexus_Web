# How to Prompt Claude Code to Implement Nexus

You can copy and paste the prompt below directly into **Claude Code** (`claude` in your terminal inside this directory `/Users/praponb/GitHub/New_Nexus_Web`):

```text
Please read the comprehensive design document in `NEXUS_DESIGN_DOCUMENT.md`.
I want you to act as the lead full-stack systems engineer and implement the entire "Nexus" web application end-to-end based on the specification.

Follow the 7 implementation phases outlined in Section 11 of NEXUS_DESIGN_DOCUMENT.md:
1. Phase 1: Set up the repository structure, Python virtual environment, dependencies, and initialize the Django backend and Nuxt 3 frontend projects.
2. Phase 2: Implement the database models (User, Project, RequirementDoc, GenerationTask, AgentStepLog, GeneratedArtifact), PostgreSQL/SQLite config, and Auth API (JWT login/register).
3. Phase 3: Implement Project CRUD, Requirement upload (accepting user_requirement.md and raw markdown), and artifact download endpoints.
4. Phase 4: Implement the autonomous 4-agent code generation pipeline in `backend/engine/` using the Google Antigravity SDK and verified MCP servers (Team Lead architect, Frontend dev, Backend dev, QA tester with Playwright self-correction loops, and packager with start_servers.sh and zip generator).
5. Phase 5: Implement real-time WebSocket log streaming using Django Channels and Redis/in-memory channel layer.
6. Phase 6: Build the modern Nuxt 3 frontend client with Tailwind CSS, dark aesthetic, Auth pages, Dashboard, Requirement intake, Mission Control live streaming cockpit, and Code Inspector/Download Hub.
7. Phase 7: Create automated test scripts (scripts/setup_environment.sh and scripts/test_agent_pipeline.sh) and verify end-to-end that an uploaded user_requirement.md yields a downloadable, working full-stack web application archive.

Work methodically phase by phase. After completing each phase, test and verify your code before proceeding to the next. Let's begin with Phase 1!
```
