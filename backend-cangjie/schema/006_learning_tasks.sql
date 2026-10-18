CREATE TABLE IF NOT EXISTS learning_tasks (
 id VARCHAR(36) PRIMARY KEY,
 user_id VARCHAR(36) NOT NULL,
 question_id VARCHAR(36) NOT NULL,
 session_id VARCHAR(36),
 input_fingerprint VARCHAR(64) NOT NULL,
 status VARCHAR(30) NOT NULL,
 version INTEGER NOT NULL DEFAULT 1,
 step_id VARCHAR(36) NOT NULL,
 checkpoint JSON NOT NULL,
 student_view JSON NOT NULL,
 pending_action JSON NOT NULL,
 active_request VARCHAR(80),
 lease_token VARCHAR(36),
 lease_until DATETIME(6),
 run_count INTEGER NOT NULL DEFAULT 0,
 cancel_requested BOOL NOT NULL DEFAULT 0,
 learning_applied BOOL NOT NULL DEFAULT 0,
 exit_reason VARCHAR(80) NOT NULL DEFAULT '',
 created_at DATETIME(6) NOT NULL,
 updated_at DATETIME(6) NOT NULL,
 INDEX ix_learning_task_queue (status,lease_until,created_at),
 INDEX ix_learning_task_owner (user_id,question_id,created_at),
 FOREIGN KEY(user_id) REFERENCES users(id),
 FOREIGN KEY(question_id) REFERENCES questions(id),
 FOREIGN KEY(session_id) REFERENCES tutor_sessions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS learning_task_requests (
 user_id VARCHAR(36) NOT NULL,
 request_id VARCHAR(80) NOT NULL,
 task_id VARCHAR(36) NOT NULL,
 body_hash VARCHAR(64) NOT NULL,
 created_at DATETIME(6) NOT NULL,
 PRIMARY KEY(user_id,request_id),
 FOREIGN KEY(user_id) REFERENCES users(id),
 FOREIGN KEY(task_id) REFERENCES learning_tasks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS learning_task_actions (
 id VARCHAR(36) PRIMARY KEY,
 task_id VARCHAR(36) NOT NULL,
 request_id VARCHAR(80) NOT NULL,
 body_hash VARCHAR(64) NOT NULL,
 kind VARCHAR(30) NOT NULL,
 input_version INTEGER NOT NULL,
 input_step_id VARCHAR(36) NOT NULL,
 body JSON NOT NULL,
 result JSON,
 status VARCHAR(30) NOT NULL,
 created_at DATETIME(6) NOT NULL,
 updated_at DATETIME(6) NOT NULL,
 UNIQUE KEY uq_learning_action_request (task_id,request_id),
 FOREIGN KEY(task_id) REFERENCES learning_tasks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS learning_task_steps (
 id VARCHAR(36) PRIMARY KEY,
 task_id VARCHAR(36) NOT NULL,
 request_id VARCHAR(80) NOT NULL,
 step_no INTEGER NOT NULL,
 plan_version INTEGER NOT NULL,
 tool_name VARCHAR(80) NOT NULL,
 validation VARCHAR(30) NOT NULL,
 agent_run_id VARCHAR(36) NOT NULL,
 trace JSON NOT NULL,
 created_at DATETIME(6) NOT NULL,
 UNIQUE KEY uq_learning_step (task_id,request_id,step_no),
 FOREIGN KEY(task_id) REFERENCES learning_tasks(id),
 FOREIGN KEY(agent_run_id) REFERENCES agent_runs(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS learning_task_exposures (
 user_id VARCHAR(36) NOT NULL,
 contrast_hash VARCHAR(64) NOT NULL,
 task_id VARCHAR(36) NOT NULL,
 created_at DATETIME(6) NOT NULL,
 PRIMARY KEY(user_id,contrast_hash),
 FOREIGN KEY(user_id) REFERENCES users(id),
 FOREIGN KEY(task_id) REFERENCES learning_tasks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
