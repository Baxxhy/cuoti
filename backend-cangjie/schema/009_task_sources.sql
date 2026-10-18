CREATE TABLE IF NOT EXISTS learning_task_sources (
 task_id VARCHAR(36) PRIMARY KEY,
 schema_version VARCHAR(20) NOT NULL,
 input_fingerprint VARCHAR(64) NOT NULL,
 origin VARCHAR(30) NOT NULL,
 source JSON NOT NULL,
 created_at DATETIME(6) NOT NULL,
 FOREIGN KEY(task_id) REFERENCES learning_tasks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
