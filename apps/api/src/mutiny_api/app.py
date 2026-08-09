"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse

from mutiny_core import (
    DEFAULT_MUTATION_MODEL,
    PolicyValidationError,
    load_llm_config_from_env,
    load_project_policy,
    parse_policy_text,
    policy_set_to_public,
    resolve_policy_path,
)
from mutiny_core.regress import RegressionNotReproducibleError

from mutiny_api import __version__
from mutiny_api.db import SCHEMA_VERSION, connect
from mutiny_api.errors import (
    error_body,
    http_exception_handler,
    raise_api,
    unhandled_exception_handler,
)
from mutiny_api.logging_setup import configure_logging
from mutiny_api.repository import Repository
from mutiny_api.schemas import (
    CampaignCreateRequest,
    CampaignStartRequest,
    HealthResponse,
    MetaResponse,
    MinimizeRequest,
    PolicyContentSaveRequest,
    ProjectCreateRequest,
    RegressionSaveRequest,
    TestsRunRequest,
)
from mutiny_api.supervisor import (
    DEFAULT_SAMPLE_PROJECT,
    HARNESS_POLICY_PATH,
    CampaignSupervisor,
    EventHub,
    project_policy_payload,
    resolve_project_root,
)

log = logging.getLogger("mutiny_api")


def create_app(db_path: str | Path) -> FastAPI:
    configure_logging()
    hub = EventHub()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        conn = connect(db_path)
        repo = Repository(conn)
        supervisor = CampaignSupervisor(repo, hub)
        supervisor.set_loop(asyncio.get_running_loop())
        app.state.repo = repo
        app.state.supervisor = supervisor
        app.state.hub = hub
        app.state.db_path = str(db_path)
        log.info("mutiny_api.startup db=%s version=%s", db_path, __version__)
        yield
        conn.close()
        log.info("mutiny_api.shutdown")

    app = FastAPI(
        title="Mutiny Hosted API",
        version=__version__,
        description=(
            "Hosted control plane for Mutiny: campaigns, SSE, minimize, regressions. "
            "AI proposes; deterministic PolicyEvaluator proves. "
            "Targets: openai_agents + project_path (customer .mutiny/adapter.py) "
            "or in_process_demo (optional harness)."
        ),
        lifespan=lifespan,
    )
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=422,
            content=error_body(
                code="validation_error",
                message="request validation failed",
                status=422,
                request_id=request_id,
                details={"errors": exc.errors()},
            ),
            headers={"X-Request-Id": request_id} if request_id else None,
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Mutiny-Version"] = __version__
        log.info(
            "http",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "ms": ms,
            },
        )
        return response

    @app.get("/api/meta", response_model=MetaResponse, tags=["ops"])
    def meta() -> MetaResponse:
        return MetaResponse(version=__version__)

    @app.get("/api/health", response_model=HealthResponse, tags=["ops"])
    def health() -> HealthResponse:
        repo: Repository = app.state.repo
        db_ok = True
        latency_ms: float | None = None
        try:
            t0 = time.perf_counter()
            repo.conn.execute("SELECT 1").fetchone()
            latency_ms = round((time.perf_counter() - t0) * 1000, 3)
        except Exception:  # noqa: BLE001
            db_ok = False
        cfg = load_llm_config_from_env()
        llm_ok = bool(cfg.configured)
        model = cfg.model if llm_ok else f"unconfigured:{DEFAULT_MUTATION_MODEL}"
        mutator_mode = "featherless" if llm_ok else "template"
        running = len(repo.list_running_campaigns())
        status = "ok" if db_ok else "degraded"
        if running > 1:
            status = "degraded"
        return HealthResponse(
            status=status,
            api=True,
            db=db_ok,
            model=model,
            version=__version__,
            mutator_mode=mutator_mode,
            llm_configured=llm_ok,
            db_latency_ms=latency_ms,
            schema_version=SCHEMA_VERSION,
            max_concurrent_campaigns=1,
            running_campaigns=running,
        )

    def _resolve_policies_project(project_path: str | None) -> str:
        return (project_path or DEFAULT_SAMPLE_PROJECT).strip()

    @app.get("/api/policies", tags=["policies"])
    def list_policies(
        project_path: str | None = Query(
            None,
            description=(
                "Customer project directory (absolute or relative to Mutiny repo). "
                f"Defaults to {DEFAULT_SAMPLE_PROJECT} for local Hosted."
            ),
        ),
    ) -> dict[str, Any]:
        try:
            payload = project_policy_payload(_resolve_policies_project(project_path))
        except (ValueError, PolicyValidationError, FileNotFoundError) as exc:
            raise_api(400, "invalid_policy", str(exc))
        return {"policies": [payload], "project_path": payload["project_path"]}

    @app.get("/api/policies/content", tags=["policies"])
    def get_policy_content(
        project_path: str | None = Query(None),
    ) -> dict[str, Any]:
        """Raw policy file content for View / Edit in Hosted."""
        try:
            root = resolve_project_root(_resolve_policies_project(project_path))
            path = resolve_policy_path(root)
            content = path.read_text(encoding="utf-8")
            policy = parse_policy_text(content, source=path)
        except (ValueError, PolicyValidationError, FileNotFoundError) as exc:
            raise_api(400, "invalid_policy", str(exc))
        return {
            "project_path": str(root),
            "path": str(path),
            "format": path.suffix.lstrip(".").lower() or "yaml",
            "content": content,
            "version": policy.version,
            "policy_set": policy_set_to_public(policy),
        }

    @app.put("/api/policies/content", tags=["policies"])
    def save_policy_content(
        body: PolicyContentSaveRequest,
        project_path: str | None = Query(None),
    ) -> dict[str, Any]:
        """Validate + write policy YAML/JSON to the project policy file."""
        try:
            root = resolve_project_root(_resolve_policies_project(project_path))
            try:
                path = resolve_policy_path(root)
            except PolicyValidationError:
                path = root / "policy.yaml"
            policy = parse_policy_text(body.content, source=path)
            path.write_text(body.content, encoding="utf-8")
        except (ValueError, PolicyValidationError, FileNotFoundError, OSError) as exc:
            raise_api(400, "invalid_policy", str(exc))
        return {
            "ok": True,
            "project_path": str(root),
            "path": str(path),
            "version": policy.version,
            "policy_set": policy_set_to_public(policy),
        }

    @app.get("/api/policies/{policy_id}", tags=["policies"])
    def get_policy(
        policy_id: str,
        project_path: str | None = Query(None),
    ) -> dict[str, Any]:
        # Product: load from project (id is typically the project directory name).
        # Harness fixture kept for in_process_demo tooling only.
        if policy_id == "demo_support" and not project_path:
            data = json.loads(HARNESS_POLICY_PATH.read_text())
            return {
                "id": "demo_support",
                "path": str(HARNESS_POLICY_PATH),
                "policy_set": data,
                "note": "harness fixture — product path uses project policy.yaml",
            }
        try:
            payload = project_policy_payload(_resolve_policies_project(project_path))
        except (ValueError, PolicyValidationError, FileNotFoundError) as exc:
            raise_api(400, "invalid_policy", str(exc))
        if policy_id not in {payload["id"], "project", payload["target"]}:
            raise_api(
                404,
                "policy_not_found",
                f"unknown policy_id={policy_id}; project policy id={payload['id']}",
            )
        return payload

    @app.get("/api/projects", tags=["projects"])
    def list_projects() -> dict[str, Any]:
        repo: Repository = app.state.repo
        return {"projects": repo.list_projects()}

    @app.get("/api/projects/{project_id}", tags=["projects"])
    def get_project(project_id: str) -> dict[str, Any]:
        repo: Repository = app.state.repo
        project = repo.get_project(project_id)
        if not project:
            raise_api(404, "project_not_found", "project not found")
        campaigns = repo.list_campaigns(project_id=project_id, limit=10)
        regressions = repo.list_regressions(project_id=project_id, limit=10)
        last_run = campaigns[0] if campaigns else None
        try:
            policy = project_policy_payload(project["path"])
        except (ValueError, PolicyValidationError, FileNotFoundError) as exc:
            policy = {"error": str(exc)}
        return {
            **project,
            "policies": policy,
            "recent_campaigns": campaigns,
            "recent_regressions": regressions,
            "last_run": last_run,
            "current_adapter": project["adapter"],
        }

    @app.post("/api/projects", status_code=201, tags=["projects"])
    def create_project(body: ProjectCreateRequest) -> dict[str, Any]:
        repo: Repository = app.state.repo
        try:
            root = resolve_project_root(body.path)
            # Ensure project policy is loadable (same bar as campaign create).
            load_project_policy(root)
        except (
            ValueError,
            PolicyValidationError,
            FileNotFoundError,
            AttributeError,
            ImportError,
        ) as exc:
            raise_api(400, "invalid_project", str(exc))
        existing = repo.get_project_by_path(str(root))
        if existing:
            return existing
        name = (body.name or root.name).strip() or root.name
        return repo.create_project(
            name=name,
            path=str(root),
            adapter=body.adapter,
        )

    @app.get("/api/campaigns", tags=["campaigns"])
    def list_campaigns(
        status: str | None = Query(None),
        project_id: str | None = Query(
            None, description="Filter campaigns belonging to a project"
        ),
        project: str | None = Query(
            None,
            description="Alias for project_id (filter by registered project)",
        ),
        violation: bool | None = Query(None),
        limit: int = Query(100, ge=1, le=500),
    ) -> dict[str, Any]:
        repo: Repository = app.state.repo
        pid = project_id or project
        return {
            "campaigns": repo.list_campaigns(
                status=status,
                project_id=pid,
                violation=violation,
                limit=limit,
            )
        }

    @app.post("/api/campaigns", status_code=201, tags=["campaigns"])
    def create_campaign(body: CampaignCreateRequest) -> dict[str, Any]:
        supervisor: CampaignSupervisor = app.state.supervisor
        try:
            return supervisor.create_campaign(body.model_dump())
        except (
            ValueError,
            PolicyValidationError,
            FileNotFoundError,
            AttributeError,
            ImportError,
        ) as exc:
            raise_api(400, "invalid_project", str(exc))

    @app.get("/api/campaigns/{campaign_id}", tags=["campaigns"])
    def get_campaign(campaign_id: str) -> dict[str, Any]:
        repo: Repository = app.state.repo
        camp = repo.get_campaign(campaign_id)
        if not camp:
            raise_api(404, "campaign_not_found", "campaign not found")
        return camp

    @app.post("/api/campaigns/{campaign_id}/start", tags=["campaigns"])
    async def start_campaign(
        campaign_id: str, body: CampaignStartRequest, request: Request
    ) -> dict[str, Any]:
        supervisor: CampaignSupervisor = app.state.supervisor
        try:
            return supervisor.start_campaign(
                campaign_id,
                attestation=body.attestation,
                request_id=getattr(request.state, "request_id", None),
            )
        except PermissionError as exc:
            raise_api(403, "attestation_required", str(exc))
        except KeyError:
            raise_api(404, "campaign_not_found", "campaign not found")
        except RuntimeError as exc:
            raise_api(409, "campaign_conflict", str(exc))
        except (
            ValueError,
            PolicyValidationError,
            FileNotFoundError,
            AttributeError,
            ImportError,
        ) as exc:
            raise_api(400, "invalid_project", str(exc))

    @app.get("/api/campaigns/{campaign_id}/candidates", tags=["campaigns"])
    def list_candidates(campaign_id: str) -> dict[str, Any]:
        repo: Repository = app.state.repo
        if not repo.get_campaign(campaign_id):
            raise_api(404, "campaign_not_found", "campaign not found")
        return {"candidates": repo.list_candidates(campaign_id)}

    @app.get("/api/campaigns/{campaign_id}/events", tags=["campaigns"])
    async def campaign_events(
        campaign_id: str,
        request: Request,
        after_id: int = Query(0),
    ) -> StreamingResponse:
        repo: Repository = app.state.repo
        hub_ref: EventHub = app.state.hub
        if not repo.get_campaign(campaign_id):
            raise_api(404, "campaign_not_found", "campaign not found")

        async def gen() -> AsyncIterator[str]:
            for ev in repo.list_events(campaign_id, after_id=after_id):
                yield f"data: {json.dumps(ev)}\n\n"
            q = await hub_ref.subscribe(campaign_id)
            try:
                yield (
                    "data: "
                    + json.dumps({"type": "ready", "campaign_id": campaign_id})
                    + "\n\n"
                )
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(q.get(), timeout=1.0)
                        yield f"data: {json.dumps(event)}\n\n"
                    except TimeoutError:
                        yield ": ping\n\n"
                        camp = repo.get_campaign(campaign_id)
                        if camp and camp["status"] not in {"created", "running"}:
                            while not q.empty():
                                event = q.get_nowait()
                                yield f"data: {json.dumps(event)}\n\n"
                            break
            finally:
                await hub_ref.unsubscribe(campaign_id, q)

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/candidates/{candidate_id}", tags=["candidates"])
    def get_candidate(candidate_id: str) -> dict[str, Any]:
        repo: Repository = app.state.repo
        cand = repo.get_candidate(candidate_id)
        if not cand:
            raise_api(404, "candidate_not_found", "candidate not found")
        return cand

    @app.post("/api/candidates/{candidate_id}/minimize", tags=["candidates"])
    def minimize(
        candidate_id: str, body: MinimizeRequest | None = None
    ) -> dict[str, Any]:
        supervisor: CampaignSupervisor = app.state.supervisor
        body = body or MinimizeRequest()
        try:
            return supervisor.minimize_candidate(
                candidate_id, target_rule_ids=body.target_rule_ids
            )
        except KeyError:
            raise_api(404, "candidate_not_found", "candidate not found")

    @app.post(
        "/api/candidates/{candidate_id}/regression",
        status_code=201,
        tags=["regressions"],
    )
    def create_regression(
        candidate_id: str, body: RegressionSaveRequest
    ) -> dict[str, Any]:
        supervisor: CampaignSupervisor = app.state.supervisor
        try:
            return supervisor.save_candidate_regression(
                candidate_id,
                name=body.name,
                target_rule_ids=body.target_rule_ids,
            )
        except KeyError:
            raise_api(404, "candidate_not_found", "candidate not found")
        except RegressionNotReproducibleError as exc:
            raise_api(400, "not_reproducible", str(exc))

    @app.get("/api/regressions", tags=["regressions"])
    def list_regressions(
        project_id: str | None = Query(None),
        with_last_run: bool = Query(True),
    ) -> dict[str, Any]:
        repo: Repository = app.state.repo
        return {
            "regressions": repo.list_regressions(
                project_id=project_id, with_last_run=with_last_run
            )
        }

    @app.get("/api/regressions/{regression_id}", tags=["regressions"])
    def get_regression(regression_id: str) -> dict[str, Any]:
        repo: Repository = app.state.repo
        row = repo.get_regression(regression_id, with_runs=True)
        if not row:
            raise_api(404, "regression_not_found", "regression not found")
        return row

    @app.delete("/api/regressions/{regression_id}", tags=["regressions"])
    def delete_regression(regression_id: str) -> dict[str, Any]:
        repo: Repository = app.state.repo
        if not repo.delete_regression(regression_id):
            raise_api(404, "regression_not_found", "regression not found")
        return {"deleted": True, "id": regression_id}

    @app.get("/api/regressions/{regression_id}/runs", tags=["tests"])
    def list_regression_runs(
        regression_id: str,
        limit: int = Query(50, ge=1, le=500),
    ) -> dict[str, Any]:
        repo: Repository = app.state.repo
        if not repo.get_regression(regression_id):
            raise_api(404, "regression_not_found", "regression not found")
        return {
            "runs": repo.list_test_runs(regression_id=regression_id, limit=limit)
        }

    @app.get("/api/tests/summary", tags=["tests"])
    def tests_summary() -> dict[str, Any]:
        repo: Repository = app.state.repo
        return repo.tests_summary()

    @app.get("/api/tests/runs", tags=["tests"])
    def list_test_runs(
        regression_id: str | None = Query(None),
        status: str | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
    ) -> dict[str, Any]:
        repo: Repository = app.state.repo
        return {
            "runs": repo.list_test_runs(
                regression_id=regression_id, status=status, limit=limit
            )
        }

    @app.post("/api/tests/run", tags=["tests"])
    def run_tests(body: TestsRunRequest) -> dict[str, Any]:
        supervisor: CampaignSupervisor = app.state.supervisor
        try:
            return supervisor.run_tests(
                body.regression_id,
                fixed_agent=body.fixed_agent,
                regression_ids=body.regression_ids,
                run_all=body.run_all,
                failed_only=body.failed_only,
                persist=body.persist,
            )
        except KeyError:
            raise_api(404, "regression_not_found", "regression not found")
        except ValueError as exc:
            raise_api(400, "invalid_tests_run", str(exc))

    return app
