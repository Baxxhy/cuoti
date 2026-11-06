CREATE TABLE IF NOT EXISTS learning_self_checks (
 id VARCHAR(36) PRIMARY KEY,
 user_id VARCHAR(36) NOT NULL,
 question_id VARCHAR(36) NOT NULL,
 task_id VARCHAR(36) NOT NULL,
 input_fingerprint VARCHAR(64) NOT NULL,
 text VARCHAR(300) NOT NULL,
 version INTEGER NOT NULL,
 deleted BOOL NOT NULL DEFAULT 0,
 created_at DATETIME(6) NOT NULL,
 updated_at DATETIME(6) NOT NULL,
 UNIQUE KEY uq_self_check_task (user_id,task_id),
 INDEX ix_self_check_question (user_id,question_id,updated_at),
 FOREIGN KEY(user_id) REFERENCES users(id),
 FOREIGN KEY(question_id) REFERENCES questions(id),
 FOREIGN KEY(task_id) REFERENCES learning_tasks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
