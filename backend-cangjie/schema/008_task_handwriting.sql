CREATE TABLE IF NOT EXISTS learning_task_images (
 id VARCHAR(36) PRIMARY KEY,
 task_id VARCHAR(36) NOT NULL,
 request_id VARCHAR(80) NOT NULL,
 input_fingerprint VARCHAR(64) NOT NULL,
 upload_step_id VARCHAR(36) NOT NULL,
 confirmation_step_id VARCHAR(36),
 original_path VARCHAR(500) NOT NULL,
 sha256 VARCHAR(64) NOT NULL,
 recognition JSON,
 created_at DATETIME(6) NOT NULL,
 updated_at DATETIME(6) NOT NULL,
 UNIQUE KEY uq_task_image_request(task_id,request_id),
 FOREIGN KEY(task_id) REFERENCES learning_tasks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
