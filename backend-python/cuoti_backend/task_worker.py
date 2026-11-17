"""Run one leased learning task using existing algorithms and MySQL transactions."""

import base64
import hashlib
import logging
from copy import deepcopy

from sqlalchemy.exc import SQLAlchemyError

from .lessons import compact
from .protocol import ApiError
from .question_data import execute, select_rows
from .task_budget import TaskBudget, TaskBudgetExceeded, stopped_view
from .task_context import prepare_context
from .task_leases import claim_lease, lease_valid
from .task_results import save_result
from .task_sources import capture_source, load_snapshot, source_equal, validate_version

logger = logging.getLogger("cuoti.backend")


def compute_action(db, media, task):
    action = deepcopy(task.get("pending_action") or {})
    if action.get("kind") != "recognize_handwriting":
        return action
    images = select_rows(
        db,
        "learning_task_images",
        "SELECT * FROM learning_task_images WHERE id=? AND task_id=? AND input_fingerprint=?",
        [action.get("handwriting_id", ""), task["id"], task["input_fingerprint"]],
    )
    if not images:
        raise ApiError(422, "这张作答照片不属于当前任务版本")
    raw = media.read(images[0]["original_path"])
    if hashlib.sha256(raw).hexdigest() != images[0]["sha256"]:
        raise ApiError(503, "作答原图校验失败，请重新上传")
    action["image_base64"] = base64.b64encode(raw).decode("ascii")
    return action


def fail_task(service, id, owner, question_id, lease, reason):
    try:
        with service.database.session() as db, db.begin():
            snapshot = load_snapshot(db, question_id, owner)
            tasks = select_rows(
                db,
                "learning_tasks",
                "SELECT * FROM learning_tasks WHERE id=? AND user_id=? FOR UPDATE",
                [id, owner],
            )
            if not tasks:
                return
            task = tasks[0]
            if not lease_valid(task, lease) or not validate_version(db, task, snapshot):
                return
            view = stopped_view("这次没能核对完成，内容已保留，可以稍后继续")
            photo = (task.get("student_view") or {}).get("handwriting")
            if photo:
                view["handwriting"] = photo
            view["secondary_actions"] = ["resume"]
            if (task.get("pending_action") or {}).get(
                "kind"
            ) == "recognize_handwriting":
                view["secondary_actions"].append("use_text")
            execute(
                db,
                "UPDATE learning_tasks SET status='failed',version=version+1,student_view=?,lease_token=NULL,lease_until=NULL,exit_reason=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?",
                [compact(view), reason, id],
            )
            execute(
                db,
                "UPDATE learning_task_actions SET status='failed',updated_at=UTC_TIMESTAMP(6) WHERE task_id=? AND request_id=? AND status='pending'",
                [id, task.get("active_request")],
            )
    except Exception:  # noqa: BLE001 -- Lease expiry permits recovery; never log private error text.
        logger.warning("learning_task_failure_save=deferred")


def run_task(service, id, *, budget=None):
    budget = budget or TaskBudget()
    lease, owner, question_id, stage = "", "", "", "claim"
    try:
        with service.database.session() as db, db.begin():
            prepared = claim_lease(db, id, budget)
        if prepared is None:
            return False
        before = prepared["task"]
        owner, question_id, lease = (
            before["user_id"],
            before["question_id"],
            prepared["lease"],
        )
        budget.check("claimed")
        stage = "image_input"
        with service.database.session() as db:
            action = compute_action(db, service.media, before)
        stage = "compute"
        seconds = budget.timeout_seconds(40, reserve_seconds=5)
        if seconds < 2:
            raise TaskBudgetExceeded("compute_reserve")
        if service.compute is None:
            raise ApiError(503, "内部算法服务未配置")
        result = service.compute.compute(
            "learning_task",
            timeout=seconds,
            task_context=prepared["context"],
            task_checkpoint=before["checkpoint"],
            task_action=action,
            task_budget_ms=38000 if seconds > 38 else (seconds - 1) * 1000,
        )
        budget.check("computed")
        stage = "commit"
        with service.database.session() as db, db.begin():
            snapshot = load_snapshot(db, question_id, owner)
            tasks = select_rows(
                db,
                "learning_tasks",
                "SELECT * FROM learning_tasks WHERE id=? AND user_id=? FOR UPDATE",
                [id, owner],
            )
            if not tasks or not lease_valid(tasks[0], lease):
                return False
            current = tasks[0]
            if not validate_version(db, current, snapshot):
                return False
            domain = prepare_context(db, capture_source(db, current, snapshot), owner)
            domain["source_snapshot_id"] = current["id"]
            domain["action_id"] = id + ":" + (current.get("active_request") or "")
            if not source_equal(prepared["context"], domain):
                raise ApiError(409, "学习依据已更新，需要重新核对")
            budget.check("validated")
            save_result(
                service,
                db,
                current,
                result,
                budget,
                domain.get("memory_snapshot") or {},
                domain,
            )
            budget.check("before_commit")
        return True
    except TaskBudgetExceeded as error:
        reason = "budget_" + error.stage
    except SQLAlchemyError as error:
        args = getattr(getattr(error, "orig", None), "args", ())
        code = str(args[0]) if args and type(args[0]) is int else "unknown"
        reason = stage + "_database_" + code
    except ApiError as error:
        reason = stage + "_api_" + str(error.status)
    except Exception:  # noqa: BLE001 -- Provider errors must not expose credentials or student text.
        reason = stage + "_runtime"
    if lease:
        fail_task(service, id, owner, question_id, lease, reason)
    return False


class LearningTaskWorker:
    """Single local poller; MySQL leases coordinate it with other processes."""

    def __init__(self, service):
        from threading import Event, Thread

        self.service = service
        self.stopping = Event()
        self.thread = Thread(target=self.loop, name="cuoti-learning-tasks", daemon=True)

    def start(self):
        self.thread.start()

    def loop(self):
        from .task_leases import recoverable_ids

        while not self.stopping.is_set():
            try:
                with self.service.database.session() as db:
                    ids = recoverable_ids(db)
                if ids and not self.stopping.is_set():
                    run_task(self.service, ids[0])
                else:
                    self.stopping.wait(1)
            except Exception:  # noqa: BLE001 -- Retry transient database errors without logging private details.
                logger.warning("learning_task_poll=deferred")
                self.stopping.wait(2)

    def close(self):
        self.stopping.set()
        if self.thread.ident is not None:
            self.thread.join()
