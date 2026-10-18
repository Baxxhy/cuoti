-- Snapshot of backend/app/models.py at d2f5e61. New isolated Cangjie databases only.

CREATE TABLE dataset_sources (
	`key` VARCHAR(80) NOT NULL,
	name VARCHAR(160) NOT NULL,
	version VARCHAR(100) NOT NULL,
	homepage VARCHAR(500) NOT NULL,
	license VARCHAR(100) NOT NULL,
	local_path VARCHAR(500) NOT NULL,
	total_items INTEGER NOT NULL,
	imported_items INTEGER NOT NULL,
	source_metadata JSON NOT NULL,
	last_imported_at DATETIME,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE UNIQUE INDEX ix_dataset_sources_key ON dataset_sources (`key`);

CREATE TABLE knowledge_points (
	code VARCHAR(100) NOT NULL,
	subject VARCHAR(30) NOT NULL,
	name VARCHAR(100) NOT NULL,
	content JSON NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE users (
	email VARCHAR(190) NOT NULL,
	name VARCHAR(100) NOT NULL,
	`role` VARCHAR(30) NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE dataset_questions (
	dataset_source_id VARCHAR(36) NOT NULL,
	source_item_id VARCHAR(190) NOT NULL,
	split VARCHAR(30) NOT NULL,
	subject VARCHAR(30) NOT NULL,
	grade VARCHAR(30) NOT NULL,
	grade_band VARCHAR(30) NOT NULL,
	title VARCHAR(255) NOT NULL,
	question_text TEXT NOT NULL,
	question_type VARCHAR(60) NOT NULL,
	options JSON NOT NULL,
	answer JSON NOT NULL,
	solution TEXT NOT NULL,
	knowledge_points JSON NOT NULL,
	image_paths JSON NOT NULL,
	difficulty VARCHAR(30) NOT NULL,
	content_hash VARCHAR(64) NOT NULL,
	source_metadata JSON NOT NULL,
	has_answer BOOL NOT NULL,
	has_solution BOOL NOT NULL,
	answer_verified BOOL NOT NULL,
	quality_status VARCHAR(30) NOT NULL,
	usable_for_practice BOOL NOT NULL,
	usable_for_auto_grade BOOL NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_dataset_question_source_item UNIQUE (dataset_source_id, source_item_id),
	FOREIGN KEY(dataset_source_id) REFERENCES dataset_sources (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_dataset_questions_content_hash ON dataset_questions (content_hash);

CREATE INDEX ix_dataset_questions_dataset_source_id ON dataset_questions (dataset_source_id);

CREATE INDEX ix_dataset_questions_grade_band ON dataset_questions (grade_band);

CREATE INDEX ix_dataset_questions_has_answer ON dataset_questions (has_answer);

CREATE INDEX ix_dataset_questions_quality_status ON dataset_questions (quality_status);

CREATE INDEX ix_dataset_questions_subject ON dataset_questions (subject);

CREATE INDEX ix_dataset_questions_usable_for_auto_grade ON dataset_questions (usable_for_auto_grade);

CREATE INDEX ix_dataset_questions_usable_for_practice ON dataset_questions (usable_for_practice);

CREATE TABLE guardian_student_links (
	guardian_id VARCHAR(36) NOT NULL,
	student_id VARCHAR(36) NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(guardian_id) REFERENCES users (id),
	FOREIGN KEY(student_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE knowledge_relations (
	source_id VARCHAR(36) NOT NULL,
	target_id VARCHAR(36) NOT NULL,
	relation_type VARCHAR(30) NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(source_id) REFERENCES knowledge_points (id),
	FOREIGN KEY(target_id) REFERENCES knowledge_points (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE mastery_states (
	user_id VARCHAR(36) NOT NULL,
	subject VARCHAR(30) NOT NULL,
	knowledge_point VARCHAR(100) NOT NULL,
	mastery_score FLOAT NOT NULL,
	confidence FLOAT NOT NULL,
	evidence_count INTEGER NOT NULL,
	near_transfer_rate FLOAT NOT NULL,
	far_transfer_rate FLOAT NOT NULL,
	forgetting_risk FLOAT NOT NULL,
	last_evidence_at DATETIME,
	update_reason TEXT NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_mastery_states_subject ON mastery_states (subject);

CREATE INDEX ix_mastery_states_user_id ON mastery_states (user_id);

CREATE TABLE misconception_states (
	user_id VARCHAR(36) NOT NULL,
	subject VARCHAR(30) NOT NULL,
	code VARCHAR(100) NOT NULL,
	label VARCHAR(150) NOT NULL,
	probability FLOAT NOT NULL,
	evidence_count INTEGER NOT NULL,
	status VARCHAR(30) NOT NULL,
	related_question_count INTEGER NOT NULL,
	successful_strategy TEXT NOT NULL,
	failed_strategy TEXT NOT NULL,
	first_seen_at DATETIME,
	last_seen_at DATETIME,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_misconception_states_subject ON misconception_states (subject);

CREATE INDEX ix_misconception_states_user_id ON misconception_states (user_id);

CREATE TABLE papers (
	user_id VARCHAR(36) NOT NULL,
	title VARCHAR(255) NOT NULL,
	filters JSON NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_papers_user_id ON papers (user_id);

CREATE TABLE questions (
	user_id VARCHAR(36) NOT NULL,
	subject VARCHAR(30) NOT NULL,
	grade VARCHAR(30),
	title VARCHAR(255) NOT NULL,
	question_text TEXT NOT NULL,
	student_answer TEXT,
	status VARCHAR(30) NOT NULL,
	confirmed BOOL NOT NULL,
	favorite BOOL NOT NULL,
	tags JSON NOT NULL,
	formulas JSON NOT NULL,
	options JSON NOT NULL,
	question_type VARCHAR(50) NOT NULL,
	knowledge_points JSON NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_questions_user_id ON questions (user_id);

CREATE TABLE student_profiles (
	user_id VARCHAR(36) NOT NULL,
	grade VARCHAR(30) NOT NULL,
	learning_goal VARCHAR(255) NOT NULL,
	preferences JSON NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (user_id),
	FOREIGN KEY(user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE teacher_audit_logs (
	teacher_id VARCHAR(36) NOT NULL,
	action VARCHAR(80) NOT NULL,
	target_type VARCHAR(50) NOT NULL,
	target_id VARCHAR(36) NOT NULL,
	before_json JSON NOT NULL,
	after_json JSON NOT NULL,
	reason TEXT NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(teacher_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_teacher_audit_logs_action ON teacher_audit_logs (action);

CREATE INDEX ix_teacher_audit_logs_target_id ON teacher_audit_logs (target_id);

CREATE INDEX ix_teacher_audit_logs_teacher_id ON teacher_audit_logs (teacher_id);

CREATE TABLE teacher_classes (
	teacher_id VARCHAR(36) NOT NULL,
	name VARCHAR(100) NOT NULL,
	grade VARCHAR(30) NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(teacher_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE cognitive_updates (
	user_id VARCHAR(36) NOT NULL,
	question_id VARCHAR(36),
	entity_type VARCHAR(30) NOT NULL,
	entity_key VARCHAR(120) NOT NULL,
	old_value FLOAT NOT NULL,
	new_value FLOAT NOT NULL,
	evidence JSON NOT NULL,
	reason TEXT NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id),
	FOREIGN KEY(question_id) REFERENCES questions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_cognitive_updates_user_id ON cognitive_updates (user_id);

CREATE TABLE dataset_practice_attempts (
	user_id VARCHAR(36) NOT NULL,
	mistake_id VARCHAR(36) NOT NULL,
	dataset_question_id VARCHAR(36) NOT NULL,
	source_dataset VARCHAR(80) NOT NULL,
	knowledge_id VARCHAR(36),
	mode VARCHAR(20) NOT NULL,
	student_answer JSON NOT NULL,
	correct BOOL NOT NULL,
	duration_seconds INTEGER NOT NULL,
	grading_details JSON NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id),
	FOREIGN KEY(mistake_id) REFERENCES questions (id),
	FOREIGN KEY(dataset_question_id) REFERENCES dataset_questions (id),
	FOREIGN KEY(knowledge_id) REFERENCES knowledge_points (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_dataset_practice_attempts_dataset_question_id ON dataset_practice_attempts (dataset_question_id);

CREATE INDEX ix_dataset_practice_attempts_mistake_id ON dataset_practice_attempts (mistake_id);

CREATE INDEX ix_dataset_practice_attempts_mode ON dataset_practice_attempts (mode);

CREATE INDEX ix_dataset_practice_attempts_source_dataset ON dataset_practice_attempts (source_dataset);

CREATE INDEX ix_dataset_practice_attempts_user_id ON dataset_practice_attempts (user_id);

CREATE TABLE diagnoses (
	question_id VARCHAR(36) NOT NULL,
	first_error_step INTEGER,
	first_error_text TEXT NOT NULL,
	error_type VARCHAR(60) NOT NULL,
	root_misconception TEXT NOT NULL,
	propagated_errors JSON NOT NULL,
	strategy_candidates JSON NOT NULL,
	confidence FLOAT NOT NULL,
	error_location TEXT NOT NULL,
	missing_prerequisites JSON NOT NULL,
	recommended_strategy TEXT NOT NULL,
	user_confirmed BOOL NOT NULL,
	correction JSON NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(question_id) REFERENCES questions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_diagnoses_question_id ON diagnoses (question_id);

CREATE TABLE export_jobs (
	paper_id VARCHAR(36) NOT NULL,
	kind VARCHAR(20) NOT NULL,
	status VARCHAR(30) NOT NULL,
	path VARCHAR(500) NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(paper_id) REFERENCES papers (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_export_jobs_paper_id ON export_jobs (paper_id);

CREATE TABLE ocr_runs (
	question_id VARCHAR(36) NOT NULL,
	provider VARCHAR(100) NOT NULL,
	raw_result JSON NOT NULL,
	confidence FLOAT NOT NULL,
	stream VARCHAR(30) NOT NULL,
	status VARCHAR(30) NOT NULL,
	model_name VARCHAR(120) NOT NULL,
	duration_ms INTEGER NOT NULL,
	error TEXT,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(question_id) REFERENCES questions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_ocr_runs_question_id ON ocr_runs (question_id);

CREATE TABLE paper_items (
	paper_id VARCHAR(36) NOT NULL,
	question_id VARCHAR(36) NOT NULL,
	position INTEGER NOT NULL,
	score INTEGER NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(paper_id) REFERENCES papers (id),
	FOREIGN KEY(question_id) REFERENCES questions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_paper_items_paper_id ON paper_items (paper_id);

CREATE TABLE practice_recommendations (
	user_id VARCHAR(36) NOT NULL,
	mistake_id VARCHAR(36) NOT NULL,
	dataset_question_id VARCHAR(36) NOT NULL,
	mode VARCHAR(20) NOT NULL,
	retrieval_rank INTEGER NOT NULL,
	retrieval_trace JSON NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id),
	FOREIGN KEY(mistake_id) REFERENCES questions (id),
	FOREIGN KEY(dataset_question_id) REFERENCES dataset_questions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_practice_recommendations_dataset_question_id ON practice_recommendations (dataset_question_id);

CREATE INDEX ix_practice_recommendations_mistake_id ON practice_recommendations (mistake_id);

CREATE INDEX ix_practice_recommendations_mode ON practice_recommendations (mode);

CREATE INDEX ix_practice_recommendations_user_id ON practice_recommendations (user_id);

CREATE TABLE problem_analyses (
	question_id VARCHAR(36) NOT NULL,
	subject VARCHAR(30) NOT NULL,
	problem_type VARCHAR(60) NOT NULL,
	known_conditions JSON NOT NULL,
	goal TEXT NOT NULL,
	knowledge_points JSON NOT NULL,
	prerequisites JSON NOT NULL,
	final_answer TEXT NOT NULL,
	verified BOOL NOT NULL,
	raw_result JSON NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (question_id),
	FOREIGN KEY(question_id) REFERENCES questions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE processing_jobs (
	question_id VARCHAR(36) NOT NULL,
	kind VARCHAR(30) NOT NULL,
	status VARCHAR(30) NOT NULL,
	progress INTEGER NOT NULL,
	error TEXT,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(question_id) REFERENCES questions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_processing_jobs_question_id ON processing_jobs (question_id);

CREATE TABLE question_assets (
	question_id VARCHAR(36) NOT NULL,
	kind VARCHAR(30) NOT NULL,
	path VARCHAR(500) NOT NULL,
	sha256 VARCHAR(64) NOT NULL,
	`role` VARCHAR(40),
	bbox JSON NOT NULL,
	description TEXT,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(question_id) REFERENCES questions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_question_assets_question_id ON question_assets (question_id);

CREATE TABLE question_assignments (
	teacher_id VARCHAR(36) NOT NULL,
	question_id VARCHAR(36) NOT NULL,
	class_id VARCHAR(36),
	title VARCHAR(255) NOT NULL,
	due_at DATETIME,
	settings JSON NOT NULL,
	status VARCHAR(30) NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(teacher_id) REFERENCES users (id),
	FOREIGN KEY(question_id) REFERENCES questions (id),
	FOREIGN KEY(class_id) REFERENCES teacher_classes (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_question_assignments_class_id ON question_assignments (class_id);

CREATE INDEX ix_question_assignments_question_id ON question_assignments (question_id);

CREATE INDEX ix_question_assignments_teacher_id ON question_assignments (teacher_id);

CREATE TABLE question_knowledge_links (
	dataset_question_id VARCHAR(36) NOT NULL,
	knowledge_point_id VARCHAR(36) NOT NULL,
	`role` VARCHAR(20) NOT NULL,
	confidence FLOAT NOT NULL,
	mapping_method VARCHAR(40) NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_question_knowledge_link UNIQUE (dataset_question_id, knowledge_point_id),
	FOREIGN KEY(dataset_question_id) REFERENCES dataset_questions (id),
	FOREIGN KEY(knowledge_point_id) REFERENCES knowledge_points (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_question_knowledge_links_dataset_question_id ON question_knowledge_links (dataset_question_id);

CREATE INDEX ix_question_knowledge_links_knowledge_point_id ON question_knowledge_links (knowledge_point_id);

CREATE INDEX ix_question_knowledge_links_role ON question_knowledge_links (`role`);

CREATE TABLE review_plans (
	user_id VARCHAR(36) NOT NULL,
	question_id VARCHAR(36) NOT NULL,
	due_at DATETIME NOT NULL,
	interval_days INTEGER NOT NULL,
	reason TEXT NOT NULL,
	status VARCHAR(30) NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id),
	FOREIGN KEY(question_id) REFERENCES questions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_review_plans_question_id ON review_plans (question_id);

CREATE INDEX ix_review_plans_user_id ON review_plans (user_id);

CREATE TABLE student_works (
	question_id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	answer TEXT NOT NULL,
	explanation TEXT NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(question_id) REFERENCES questions (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_student_works_question_id ON student_works (question_id);

CREATE TABLE teacher_class_students (
	class_id VARCHAR(36) NOT NULL,
	student_id VARCHAR(36) NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_teacher_class_student UNIQUE (class_id, student_id),
	FOREIGN KEY(class_id) REFERENCES teacher_classes (id),
	FOREIGN KEY(student_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE teacher_marks (
	question_id VARCHAR(36) NOT NULL,
	mark_type VARCHAR(50) NOT NULL,
	comment TEXT NOT NULL,
	bbox JSON NOT NULL,
	confidence FLOAT NOT NULL,
	source VARCHAR(50) NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(question_id) REFERENCES questions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_teacher_marks_question_id ON teacher_marks (question_id);

CREATE TABLE teacher_questions (
	question_id VARCHAR(36) NOT NULL,
	teacher_id VARCHAR(36) NOT NULL,
	source_type VARCHAR(30) NOT NULL,
	standard_answer TEXT NOT NULL,
	reference_steps JSON NOT NULL,
	scoring_points JSON NOT NULL,
	difficulty VARCHAR(30) NOT NULL,
	allow_auto_grade BOOL NOT NULL,
	require_handwriting BOOL NOT NULL,
	status VARCHAR(30) NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(question_id) REFERENCES questions (id),
	FOREIGN KEY(teacher_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE UNIQUE INDEX ix_teacher_questions_question_id ON teacher_questions (question_id);

CREATE INDEX ix_teacher_questions_teacher_id ON teacher_questions (teacher_id);

CREATE TABLE teacher_review_tasks (
	class_id VARCHAR(36) NOT NULL,
	student_id VARCHAR(36) NOT NULL,
	question_id VARCHAR(36) NOT NULL,
	source_type VARCHAR(30) NOT NULL,
	source_id VARCHAR(36) NOT NULL,
	status VARCHAR(30) NOT NULL,
	reason_codes JSON NOT NULL,
	ai_result JSON NOT NULL,
	rule_result JSON NOT NULL,
	confidence FLOAT NOT NULL,
	has_conflict BOOL NOT NULL,
	assigned_teacher_id VARCHAR(36),
	version INTEGER NOT NULL,
	learning_applied BOOL NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_teacher_review_source UNIQUE (source_type, source_id),
	FOREIGN KEY(class_id) REFERENCES teacher_classes (id),
	FOREIGN KEY(student_id) REFERENCES users (id),
	FOREIGN KEY(question_id) REFERENCES questions (id),
	FOREIGN KEY(assigned_teacher_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_teacher_review_tasks_class_id ON teacher_review_tasks (class_id);

CREATE INDEX ix_teacher_review_tasks_question_id ON teacher_review_tasks (question_id);

CREATE INDEX ix_teacher_review_tasks_source_id ON teacher_review_tasks (source_id);

CREATE INDEX ix_teacher_review_tasks_status ON teacher_review_tasks (status);

CREATE INDEX ix_teacher_review_tasks_student_id ON teacher_review_tasks (student_id);

CREATE TABLE tutor_sessions (
	user_id VARCHAR(36) NOT NULL,
	question_id VARCHAR(36) NOT NULL,
	stage VARCHAR(50) NOT NULL,
	hint_level INTEGER NOT NULL,
	turn_count INTEGER NOT NULL,
	mastery_score FLOAT NOT NULL,
	state JSON NOT NULL,
	status VARCHAR(30) NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id),
	FOREIGN KEY(question_id) REFERENCES questions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_tutor_sessions_question_id ON tutor_sessions (question_id);

CREATE INDEX ix_tutor_sessions_user_id ON tutor_sessions (user_id);

CREATE TABLE user_question_knowledge_links (
	user_id VARCHAR(36) NOT NULL,
	question_id VARCHAR(36) NOT NULL,
	knowledge_point_id VARCHAR(36) NOT NULL,
	`role` VARCHAR(20) NOT NULL,
	confidence FLOAT NOT NULL,
	mapping_method VARCHAR(40) NOT NULL,
	evidence_text VARCHAR(255) NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_user_question_knowledge_link UNIQUE (question_id, knowledge_point_id),
	FOREIGN KEY(user_id) REFERENCES users (id),
	FOREIGN KEY(question_id) REFERENCES questions (id),
	FOREIGN KEY(knowledge_point_id) REFERENCES knowledge_points (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_user_question_knowledge_links_knowledge_point_id ON user_question_knowledge_links (knowledge_point_id);

CREATE INDEX ix_user_question_knowledge_links_question_id ON user_question_knowledge_links (question_id);

CREATE INDEX ix_user_question_knowledge_links_role ON user_question_knowledge_links (`role`);

CREATE INDEX ix_user_question_knowledge_links_user_id ON user_question_knowledge_links (user_id);

CREATE TABLE agent_runs (
	session_id VARCHAR(36),
	agent_name VARCHAR(80) NOT NULL,
	status VARCHAR(30) NOT NULL,
	result JSON NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(session_id) REFERENCES tutor_sessions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE assignment_students (
	assignment_id VARCHAR(36) NOT NULL,
	student_id VARCHAR(36) NOT NULL,
	status VARCHAR(30) NOT NULL,
	latest_attempt_id VARCHAR(36),
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_assignment_student UNIQUE (assignment_id, student_id),
	FOREIGN KEY(assignment_id) REFERENCES question_assignments (id),
	FOREIGN KEY(student_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_assignment_students_assignment_id ON assignment_students (assignment_id);

CREATE INDEX ix_assignment_students_student_id ON assignment_students (student_id);

CREATE TABLE reference_steps (
	analysis_id VARCHAR(36) NOT NULL,
	step_index INTEGER NOT NULL,
	text TEXT NOT NULL,
	expression TEXT,
	explanation TEXT NOT NULL,
	math_valid BOOL NOT NULL,
	uses_condition BOOL NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(analysis_id) REFERENCES problem_analyses (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_reference_steps_analysis_id ON reference_steps (analysis_id);

CREATE TABLE review_records (
	plan_id VARCHAR(36) NOT NULL,
	grade VARCHAR(20) NOT NULL,
	correct BOOL NOT NULL,
	student_answer TEXT NOT NULL,
	expected_answer TEXT NOT NULL,
	feedback TEXT NOT NULL,
	score INTEGER NOT NULL,
	grading_details JSON NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(plan_id) REFERENCES review_plans (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_review_records_plan_id ON review_records (plan_id);

CREATE TABLE student_steps (
	work_id VARCHAR(36) NOT NULL,
	step_index INTEGER NOT NULL,
	text TEXT NOT NULL,
	bbox JSON NOT NULL,
	raw_text TEXT NOT NULL,
	normalized_text TEXT NOT NULL,
	formula TEXT NOT NULL,
	confidence FLOAT NOT NULL,
	source VARCHAR(50) NOT NULL,
	user_confirmed BOOL NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(work_id) REFERENCES student_works (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_student_steps_work_id ON student_steps (work_id);

CREATE TABLE teacher_review_results (
	task_id VARCHAR(36) NOT NULL,
	teacher_id VARCHAR(36) NOT NULL,
	conclusion VARCHAR(30) NOT NULL,
	score FLOAT,
	reason TEXT NOT NULL,
	first_key_error TEXT NOT NULL,
	error_type VARCHAR(80) NOT NULL,
	propagated_error BOOL NOT NULL,
	student_hint TEXT NOT NULL,
	next_task TEXT NOT NULL,
	mastered_steps JSON NOT NULL,
	allow_learning_update BOOL NOT NULL,
	evidence_snapshot JSON NOT NULL,
	learning_snapshot JSON NOT NULL,
	supersedes_id VARCHAR(36),
	revoked_at DATETIME,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(task_id) REFERENCES teacher_review_tasks (id),
	FOREIGN KEY(teacher_id) REFERENCES users (id),
	FOREIGN KEY(supersedes_id) REFERENCES teacher_review_results (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_teacher_review_results_task_id ON teacher_review_results (task_id);

CREATE INDEX ix_teacher_review_results_teacher_id ON teacher_review_results (teacher_id);

CREATE TABLE tutor_turns (
	session_id VARCHAR(36) NOT NULL,
	`role` VARCHAR(20) NOT NULL,
	content TEXT NOT NULL,
	stage VARCHAR(50) NOT NULL,
	metadata_json JSON NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(session_id) REFERENCES tutor_sessions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_tutor_turns_session_id ON tutor_turns (session_id);

CREATE TABLE variant_questions (
	question_id VARCHAR(36) NOT NULL,
	session_id VARCHAR(36) NOT NULL,
	transfer_type VARCHAR(20) NOT NULL,
	question_text TEXT NOT NULL,
	answer TEXT NOT NULL,
	explanation TEXT NOT NULL,
	reference_solution JSON NOT NULL,
	verified BOOL NOT NULL,
	generation_metadata JSON NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(question_id) REFERENCES questions (id),
	FOREIGN KEY(session_id) REFERENCES tutor_sessions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_variant_questions_question_id ON variant_questions (question_id);

CREATE INDEX ix_variant_questions_session_id ON variant_questions (session_id);

CREATE TABLE visualization_specs (
	session_id VARCHAR(36) NOT NULL,
	type VARCHAR(60) NOT NULL,
	title VARCHAR(255) NOT NULL,
	spec JSON NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(session_id) REFERENCES tutor_sessions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_visualization_specs_session_id ON visualization_specs (session_id);

CREATE TABLE voice_records (
	user_id VARCHAR(36) NOT NULL,
	question_id VARCHAR(36),
	work_id VARCHAR(36),
	kind VARCHAR(20) NOT NULL,
	audio_path VARCHAR(500) NOT NULL,
	transcript TEXT NOT NULL,
	model_name VARCHAR(100) NOT NULL,
	status VARCHAR(30) NOT NULL,
	duration_ms INTEGER NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id),
	FOREIGN KEY(question_id) REFERENCES questions (id),
	FOREIGN KEY(work_id) REFERENCES student_works (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_voice_records_user_id ON voice_records (user_id);

CREATE TABLE agent_tool_calls (
	agent_run_id VARCHAR(36) NOT NULL,
	tool_name VARCHAR(80) NOT NULL,
	input_json JSON NOT NULL,
	output_json JSON NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(agent_run_id) REFERENCES agent_runs (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_agent_tool_calls_agent_run_id ON agent_tool_calls (agent_run_id);

CREATE TABLE assignment_attempts (
	assignment_student_id VARCHAR(36) NOT NULL,
	student_id VARCHAR(36) NOT NULL,
	question_id VARCHAR(36) NOT NULL,
	answer TEXT NOT NULL,
	steps JSON NOT NULL,
	handwriting_asset_ref VARCHAR(500),
	grading_details JSON NOT NULL,
	verdict VARCHAR(30) NOT NULL,
	status VARCHAR(30) NOT NULL,
	version INTEGER NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(assignment_student_id) REFERENCES assignment_students (id),
	FOREIGN KEY(student_id) REFERENCES users (id),
	FOREIGN KEY(question_id) REFERENCES questions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_assignment_attempts_assignment_student_id ON assignment_attempts (assignment_student_id);

CREATE INDEX ix_assignment_attempts_question_id ON assignment_attempts (question_id);

CREATE INDEX ix_assignment_attempts_student_id ON assignment_attempts (student_id);

CREATE TABLE diagnosis_evidence (
	diagnosis_id VARCHAR(36) NOT NULL,
	kind VARCHAR(50) NOT NULL,
	content TEXT NOT NULL,
	reference_step_id VARCHAR(36),
	student_step_id VARCHAR(36),
	alignment VARCHAR(50) NOT NULL,
	equivalent BOOL NOT NULL,
	uses_condition BOOL NOT NULL,
	is_first_error BOOL NOT NULL,
	propagated BOOL NOT NULL,
	math_valid BOOL NOT NULL,
	metadata_json JSON NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(diagnosis_id) REFERENCES diagnoses (id),
	FOREIGN KEY(reference_step_id) REFERENCES reference_steps (id),
	FOREIGN KEY(student_step_id) REFERENCES student_steps (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_diagnosis_evidence_diagnosis_id ON diagnosis_evidence (diagnosis_id);

CREATE TABLE variant_attempts (
	variant_id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	answer TEXT NOT NULL,
	correct BOOL NOT NULL,
	elapsed_seconds INTEGER NOT NULL,
	hint_level INTEGER NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(variant_id) REFERENCES variant_questions (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_variant_attempts_variant_id ON variant_attempts (variant_id);

CREATE TABLE visualization_interactions (
	visualization_id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	`values` JSON NOT NULL,
	observation TEXT NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(visualization_id) REFERENCES visualization_specs (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_visualization_interactions_visualization_id ON visualization_interactions (visualization_id);
