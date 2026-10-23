CREATE TABLE IF NOT EXISTS knowledge_lessons (
 id VARCHAR(36) PRIMARY KEY,
 user_id VARCHAR(36) NOT NULL,
 knowledge_code VARCHAR(100) NOT NULL,
 request_id VARCHAR(80) NOT NULL,
 input_fingerprint VARCHAR(129) NOT NULL,
 prompt TEXT NOT NULL,
 result JSON NOT NULL,
 created_at DATETIME(6) NOT NULL,
 UNIQUE KEY uq_knowledge_lesson_request (user_id, request_id),
 INDEX ix_knowledge_lesson_owner (user_id, knowledge_code, created_at),
 FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS saved_review_filters (
 id VARCHAR(36) PRIMARY KEY,
 user_id VARCHAR(36) NOT NULL,
 name VARCHAR(80) NOT NULL,
 query_text VARCHAR(300) NOT NULL,
 subject VARCHAR(30) NOT NULL,
 scope VARCHAR(20) NOT NULL,
 created_at DATETIME(6) NOT NULL,
 INDEX ix_review_filter_owner (user_id, created_at),
 FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
