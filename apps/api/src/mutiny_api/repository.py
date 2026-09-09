"""Persistence repositories — API-owned SQLite only."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mutiny_core.redact import redact_secrets

# Opaque project.path prefix for observe-only ingest (never a filesystem mount).
INGEST_LOCAL_KEY_PREFIX = "local_key:"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_json_hash(value: Any) -> str:
    """SHA-256 of canonical JSON for conflict detection (not request signing)."""
    blob = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def local_key_path(local_project_key: str) -> str:
    """Store local_project_key as an opaque projects.path label."""
    return f"{INGEST_LOCAL_KEY_PREFIX}{local_project_key}"


class Repository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()

    # --- projects ---
    def create_project(
        self,
        *,
        name: str,
        path: str,
        adapter: str = "openai_agents",
        project_id: str | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        pid = project_id or str(uuid.uuid4())
        ts = _now()
        self.conn.execute(
            "INSERT INTO projects (id, name, path, adapter, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pid, name, path, adapter, ts, ts),
        )
        if commit:
            self.conn.commit()
        return self.get_project(pid)  # type: ignore[return-value]

    def upsert_project_by_path(
        self,
        path: str,
        *,
        name: str | None = None,
        adapter: str = "openai_agents",
    ) -> dict[str, Any]:
        """Return existing project for path, or create one."""
        existing = self.get_project_by_path(path)
        if existing:
            return existing
        display = name or Path(path).name or "project"
        return self.create_project(name=display, path=path, adapter=adapter)

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if not row:
            return None
        return self._project_row(row)

    def get_project_by_path(self, path: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM projects WHERE path = ?", (path,)
        ).fetchone()
        if not row:
            return None
        return self._project_row(row)

    def get_project_by_local_key(self, local_project_key: str) -> dict[str, Any] | None:
        """Lookup ingest project by opaque local_project_key (not a filesystem path)."""
        return self.get_project_by_path(local_key_path(local_project_key))

    def ensure_ingest_project(
        self,
        *,
        local_project_key: str,
        name: str | None = None,
        adapter: str = "openai_agents",
        project_id: str | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        """Create-or-return project for an opaque local key. Never touches the FS."""
        existing = self.get_project_by_local_key(local_project_key)
        if existing:
            return existing
        display = (name or local_project_key[:32] or "project").strip() or "project"
        return self.create_project(
            name=display,
            path=local_key_path(local_project_key),
            adapter=adapter,
            project_id=project_id,
            commit=commit,
        )

    def list_projects(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM projects ORDER BY updated_at DESC, created_at DESC"
        ).fetchall()
        return [self._project_row(r) for r in rows]

    def touch_project(self, project_id: str, *, commit: bool = True) -> None:
        self.conn.execute(
            "UPDATE projects SET updated_at = ? WHERE id = ?",
            (_now(), project_id),
        )
        if commit:
            self.conn.commit()

    def _project_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "path": row["path"],
            "adapter": row["adapter"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    # --- campaigns ---
    def create_campaign(
        self,
        campaign_id: str,
        config: dict[str, Any],
        *,
        project_id: str | None = None,
        status: str = "created",
        commit: bool = True,
    ) -> dict[str, Any]:
        ts = _now()
        self.conn.execute(
            "INSERT INTO campaigns "
            "(id, status, config_json, metrics_json, created_at, project_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                campaign_id,
                status,
                json.dumps(config),
                None,
                ts,
                project_id,
            ),
        )
        if project_id:
            self.conn.execute(
                "UPDATE projects SET updated_at = ? WHERE id = ?",
                (ts, project_id),
            )
        if commit:
            self.conn.commit()
        return self.get_campaign(campaign_id)  # type: ignore[return-value]

    def get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        if not row:
            return None
        return self._campaign_row(row)

    def list_campaigns(
        self,
        *,
        status: str | None = None,
        project_id: str | None = None,
        violation: bool | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("c.status = ?")
            params.append(status)
        if project_id:
            clauses.append("c.project_id = ?")
            params.append(project_id)
        if violation is True:
            clauses.append("c.status = 'violation'")
        elif violation is False:
            clauses.append("c.status != 'violation'")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(limit, 500)))
        rows = self.conn.execute(
            f"SELECT c.* FROM campaigns c {where} "
            "ORDER BY c.created_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [self._campaign_row(r) for r in rows]

    def list_running_campaigns(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM campaigns WHERE status = 'running'"
        ).fetchall()
        return [self._campaign_row(r) for r in rows]

    def update_campaign_status(
        self,
        campaign_id: str,
        status: str,
        *,
        metrics: dict[str, Any] | None = None,
        completed: bool = False,
        completed_at: str | None = None,
        commit: bool = True,
    ) -> None:
        if completed:
            self.conn.execute(
                "UPDATE campaigns SET status = ?, metrics_json = ?, completed_at = ? WHERE id = ?",
                (
                    status,
                    json.dumps(metrics) if metrics is not None else None,
                    completed_at or _now(),
                    campaign_id,
                ),
            )
        else:
            self.conn.execute(
                "UPDATE campaigns SET status = ?, metrics_json = COALESCE(?, metrics_json) WHERE id = ?",
                (
                    status,
                    json.dumps(metrics) if metrics is not None else None,
                    campaign_id,
                ),
            )
        if commit:
            self.conn.commit()

    def _campaign_row(self, row: sqlite3.Row) -> dict[str, Any]:
        # sqlite3.Row supports key access; older rows may lack project_id key
        keys = row.keys()
        project_id = row["project_id"] if "project_id" in keys else None
        metrics = json.loads(row["metrics_json"]) if row["metrics_json"] else None
        status = row["status"]
        generation = None
        if isinstance(metrics, dict):
            gens = metrics.get("generations_completed")
            if isinstance(gens, int):
                generation = gens
        violated_metric = None
        if isinstance(metrics, dict) and "violated" in metrics:
            violated_metric = bool(metrics["violated"])
        violation = status == "violation" or violated_metric is True
        project = self.get_project(project_id) if project_id else None
        return {
            "id": row["id"],
            "status": status,
            "config": json.loads(row["config_json"]),
            "metrics": metrics,
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
            "finished_at": row["completed_at"],
            "project_id": project_id,
            "project": project,
            "generation": generation,
            "violation": violation,
        }

    # --- candidates / traces ---
    def upsert_candidate(
        self,
        *,
        candidate_id: str,
        campaign_id: str,
        parent_id: str | None,
        generation: int,
        genome: dict[str, Any],
        fitness: float | None,
        status: str,
        violated: bool,
        hits: list[dict[str, Any]] | None = None,
        commit: bool = True,
    ) -> None:
        self.conn.execute(
            "INSERT INTO candidates "
            "(id, campaign_id, parent_id, generation, genome_json, fitness, status, violated, hits_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "parent_id=excluded.parent_id, generation=excluded.generation, "
            "genome_json=excluded.genome_json, fitness=excluded.fitness, "
            "status=excluded.status, violated=excluded.violated, hits_json=excluded.hits_json",
            (
                candidate_id,
                campaign_id,
                parent_id,
                generation,
                json.dumps(redact_secrets(genome)),
                fitness,
                status,
                1 if violated else 0,
                json.dumps(redact_secrets(hits or [])),
            ),
        )
        if commit:
            self.conn.commit()

    def upsert_trace(
        self, candidate_id: str, trace: dict[str, Any], *, commit: bool = True
    ) -> None:
        safe_trace = redact_secrets(trace)
        self.conn.execute(
            "INSERT INTO traces (candidate_id, trace_json) VALUES (?, ?) "
            "ON CONFLICT(candidate_id) DO UPDATE SET trace_json=excluded.trace_json",
            (candidate_id, json.dumps(safe_trace)),
        )
        if commit:
            self.conn.commit()

    def list_candidates(self, campaign_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM candidates WHERE campaign_id = ? ORDER BY generation, id",
            (campaign_id,),
        ).fetchall()
        return [self._candidate_row(r) for r in rows]

    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
        if not row:
            return None
        data = self._candidate_row(row)
        trace = self.conn.execute(
            "SELECT trace_json FROM traces WHERE candidate_id = ?", (candidate_id,)
        ).fetchone()
        data["trace"] = json.loads(trace["trace_json"]) if trace else None
        return data

    def _candidate_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "campaign_id": row["campaign_id"],
            "parent_id": row["parent_id"],
            "generation": row["generation"],
            "genome": json.loads(row["genome_json"]),
            "fitness": row["fitness"],
            "status": row["status"],
            "violated": bool(row["violated"]),
            "hits": json.loads(row["hits_json"]) if row["hits_json"] else [],
        }

    # --- events ---
    def append_event(
        self,
        campaign_id: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        client_event_id: str | None = None,
        ts: str | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        event_ts = ts or _now()
        safe_payload = redact_secrets(payload)
        payload_hash = stable_json_hash({"type": event_type, "payload": safe_payload})
        if client_event_id:
            existing = self.get_event_by_client_id(campaign_id, client_event_id)
            if existing is not None:
                existing_hash = existing.get("payload_hash") or stable_json_hash(
                    {"type": existing["type"], "payload": existing["payload"]}
                )
                if existing_hash != payload_hash:
                    raise LookupError("event_conflict")
                # Same identity + same body → idempotent no-op
                return {
                    "id": existing["id"],
                    "campaign_id": campaign_id,
                    "ts": existing["ts"],
                    "type": existing["type"],
                    "payload": existing["payload"],
                    "client_event_id": client_event_id,
                    "duplicate": True,
                }
        cur = self.conn.execute(
            "INSERT INTO events "
            "(campaign_id, ts, type, payload_json, client_event_id, payload_hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                campaign_id,
                event_ts,
                event_type,
                json.dumps(safe_payload),
                client_event_id,
                payload_hash,
            ),
        )
        if commit:
            self.conn.commit()
        return {
            "id": cur.lastrowid,
            "campaign_id": campaign_id,
            "ts": event_ts,
            "type": event_type,
            "payload": safe_payload,
            "client_event_id": client_event_id,
            "duplicate": False,
        }

    def get_event_by_client_id(
        self, campaign_id: str, client_event_id: str
    ) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM events WHERE campaign_id = ? AND client_event_id = ?",
            (campaign_id, client_event_id),
        ).fetchone()
        if not row:
            return None
        keys = row.keys()
        return {
            "id": row["id"],
            "campaign_id": row["campaign_id"],
            "ts": row["ts"],
            "type": row["type"],
            "payload": json.loads(row["payload_json"]),
            "client_event_id": row["client_event_id"]
            if "client_event_id" in keys
            else None,
            "payload_hash": row["payload_hash"] if "payload_hash" in keys else None,
        }

    def list_events(
        self, campaign_id: str, *, after_id: int = 0
    ) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM events WHERE campaign_id = ? AND id > ? ORDER BY id",
            (campaign_id, after_id),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "campaign_id": r["campaign_id"],
                "ts": r["ts"],
                "type": r["type"],
                "payload": json.loads(r["payload_json"]),
            }
            for r in rows
        ]

    # --- regressions ---
    def save_regression(
        self,
        reg_id: str,
        *,
        campaign_id: str | None,
        candidate_id: str | None,
        path: str | None,
        artifact: dict[str, Any],
        commit: bool = True,
    ) -> dict[str, Any]:
        ts = _now()
        safe_artifact = redact_secrets(artifact)
        self.conn.execute(
            "INSERT INTO regressions (id, campaign_id, candidate_id, path, artifact_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                reg_id,
                campaign_id,
                candidate_id,
                path,
                json.dumps(safe_artifact),
                ts,
            ),
        )
        if commit:
            self.conn.commit()
        return self.get_regression(reg_id)  # type: ignore[return-value]

    def upsert_regression_ingest(
        self,
        reg_id: str,
        *,
        campaign_id: str | None,
        candidate_id: str | None,
        path: str | None,
        artifact: dict[str, Any],
        commit: bool = True,
    ) -> tuple[dict[str, Any], bool]:
        """Create-or-return regression. Returns (row, created). Raises LookupError on conflict."""
        existing = self.get_regression(reg_id)
        safe_artifact = redact_secrets(artifact)
        if existing:
            if stable_json_hash(existing["artifact"]) != stable_json_hash(safe_artifact):
                raise LookupError("regression_conflict")
            # Also conflict if campaign/candidate linkage diverges materially
            if campaign_id and existing.get("campaign_id") not in (None, campaign_id):
                raise LookupError("regression_conflict")
            if candidate_id and existing.get("candidate_id") not in (None, candidate_id):
                raise LookupError("regression_conflict")
            return existing, False
        return (
            self.save_regression(
                reg_id,
                campaign_id=campaign_id,
                candidate_id=candidate_id,
                path=path,
                artifact=safe_artifact,
                commit=commit,
            ),
            True,
        )

    def get_regression(
        self, reg_id: str, *, with_runs: bool = False, runs_limit: int = 50
    ) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM regressions WHERE id = ?", (reg_id,)
        ).fetchone()
        if not row:
            return None
        out = self._regression_row(row)
        if with_runs:
            out["last_run"] = self.get_latest_test_run(reg_id)
            out["runs"] = self.list_test_runs(
                regression_id=reg_id, limit=runs_limit
            )
        return out

    def list_regressions(
        self,
        *,
        project_id: str | None = None,
        limit: int | None = None,
        with_last_run: bool = False,
    ) -> list[dict[str, Any]]:
        params: list[Any] = []
        if project_id:
            sql = (
                "SELECT r.* FROM regressions r "
                "JOIN campaigns c ON c.id = r.campaign_id "
                "WHERE c.project_id = ? "
                "ORDER BY r.created_at DESC"
            )
            params.append(project_id)
        else:
            sql = "SELECT * FROM regressions ORDER BY created_at DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(max(1, min(limit, 500)))
        rows = self.conn.execute(sql, params).fetchall()
        out = [self._regression_row(r) for r in rows]
        if with_last_run:
            for item in out:
                item["last_run"] = self.get_latest_test_run(item["id"])
        return out

    def delete_regression(self, reg_id: str) -> bool:
        cur = self.conn.execute("DELETE FROM regressions WHERE id = ?", (reg_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def _regression_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "campaign_id": row["campaign_id"],
            "candidate_id": row["candidate_id"],
            "path": row["path"],
            "artifact": json.loads(row["artifact_json"]),
            "created_at": row["created_at"],
        }

    # --- test runs (Milestone D) ---
    def save_test_run(
        self,
        run_id: str,
        *,
        regression_id: str,
        status: str,
        duration_ms: float | None,
        policy_version: str | None,
        agent_version: str | None,
        fixed_agent: bool,
        violated_rule_ids: list[str],
        evidence: list[dict[str, Any]],
        summary: str | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        ts = _now()
        self.conn.execute(
            "INSERT INTO test_runs ("
            "id, regression_id, status, duration_ms, policy_version, agent_version, "
            "fixed_agent, violated_rule_ids_json, evidence_json, summary, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                regression_id,
                status,
                duration_ms,
                policy_version,
                agent_version,
                1 if fixed_agent else 0,
                json.dumps(violated_rule_ids),
                json.dumps(redact_secrets(evidence)),
                summary,
                ts,
            ),
        )
        if commit:
            self.conn.commit()
        return self.get_test_run(run_id)  # type: ignore[return-value]

    def upsert_test_run_ingest(
        self,
        run_id: str,
        *,
        regression_id: str,
        status: str,
        duration_ms: float | None,
        policy_version: str | None,
        agent_version: str | None,
        fixed_agent: bool,
        violated_rule_ids: list[str],
        evidence: list[dict[str, Any]],
        summary: str | None = None,
        commit: bool = True,
    ) -> tuple[dict[str, Any], bool]:
        """Create-or-return test run. Raises LookupError on divergent identity."""
        existing = self.get_test_run(run_id)
        safe_evidence = redact_secrets(evidence)
        if existing:
            fingerprint = {
                "regression_id": regression_id,
                "status": status,
                "violated_rule_ids": violated_rule_ids,
                "evidence": safe_evidence,
                "summary": summary,
                "fixed_agent": fixed_agent,
            }
            existing_fp = {
                "regression_id": existing["regression_id"],
                "status": existing["status"],
                "violated_rule_ids": existing["violated_rule_ids"],
                "evidence": existing["evidence"],
                "summary": existing["summary"],
                "fixed_agent": existing["fixed_agent"],
            }
            if stable_json_hash(fingerprint) != stable_json_hash(existing_fp):
                raise LookupError("test_run_conflict")
            return existing, False
        return (
            self.save_test_run(
                run_id,
                regression_id=regression_id,
                status=status,
                duration_ms=duration_ms,
                policy_version=policy_version,
                agent_version=agent_version,
                fixed_agent=fixed_agent,
                violated_rule_ids=violated_rule_ids,
                evidence=safe_evidence,
                summary=summary,
                commit=commit,
            ),
            True,
        )

    def get_test_run(self, run_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM test_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if not row:
            return None
        return self._test_run_row(row)

    def get_latest_test_run(self, regression_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM test_runs WHERE regression_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (regression_id,),
        ).fetchone()
        if not row:
            return None
        return self._test_run_row(row)

    def list_test_runs(
        self,
        *,
        regression_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if regression_id:
            clauses.append("regression_id = ?")
            params.append(regression_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            f"SELECT * FROM test_runs {where} "
            "ORDER BY created_at DESC LIMIT ?"
        )
        params.append(max(1, min(limit, 500)))
        rows = self.conn.execute(sql, params).fetchall()
        return [self._test_run_row(r) for r in rows]

    def tests_summary(self) -> dict[str, Any]:
        regs = self.list_regressions(with_last_run=True)
        total = len(regs)
        passed = 0
        failed = 0
        never = 0
        for r in regs:
            last = r.get("last_run")
            if not last:
                never += 1
            elif last.get("status") == "PASS":
                passed += 1
            elif last.get("status") == "FAIL":
                failed += 1
            else:
                never += 1
        recent = self.list_test_runs(limit=20)
        rate = round((passed / total) * 100, 1) if total else None
        return {
            "regression_count": total,
            "passed": passed,
            "failed": failed,
            "never_run": never,
            "pass_rate": rate,
            "recent_runs": recent,
            "failed_regressions": [
                r for r in regs if (r.get("last_run") or {}).get("status") == "FAIL"
            ],
        }

    def _test_run_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "regression_id": row["regression_id"],
            "status": row["status"],
            "duration_ms": row["duration_ms"],
            "policy_version": row["policy_version"],
            "agent_version": row["agent_version"],
            "fixed_agent": bool(row["fixed_agent"]),
            "violated_rule_ids": json.loads(row["violated_rule_ids_json"] or "[]"),
            "evidence": json.loads(row["evidence_json"] or "[]"),
            "summary": row["summary"],
            "created_at": row["created_at"],
        }
