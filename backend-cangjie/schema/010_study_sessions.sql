CREATE TABLE IF NOT EXISTS study_sessions (
 id VARCHAR(36) PRIMARY KEY,
 user_id VARCHAR(36) NOT NULL,
 mode VARCHAR(20) NOT NULL,
 title VARCHAR(255) NOT NULL,
 subject VARCHAR(30) NOT NULL,
 grade_band VARCHAR(30) NOT NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'active',
 duration_seconds INT NOT NULL,
 deadline_at DATETIME(6) NULL,
 version INT NOT NULL DEFAULT 1,
 results JSON NULL,
 created_at DATETIME(6) NOT NULL,
 updated_at DATETIME(6) NOT NULL,
 submitted_at DATETIME(6) NULL,
 INDEX ix_study_owner (user_id, created_at),
 FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS study_session_items (
 id VARCHAR(36) PRIMARY KEY,
 session_id VARCHAR(36) NOT NULL,
 position INT NOT NULL,
 snapshot JSON NOT NULL,
 student_answer JSON NULL,
 grading JSON NULL,
 UNIQUE KEY uq_study_position (session_id, position),
 FOREIGN KEY (session_id) REFERENCES study_sessions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
