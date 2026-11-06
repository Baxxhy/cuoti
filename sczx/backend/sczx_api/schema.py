"""Initialize only an empty, isolated migration database using the original schema."""
from pathlib import Path
from .database import Database

SCHEMA = Path(__file__).resolve().parents[1] / 'schema'


def initialize_database():
    with Database.from_environment() as db:
        if db.query('SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE()').rows:
            raise ValueError('初始化只允许空数据库')
        for sql_file in sorted(SCHEMA.glob('*.sql')):
            for statement in sql_file.read_text().split(';'):
                if statement.strip():
                    db.query(statement)
        for table in ['student_works', 'diagnoses', 'tutor_turns', 'practice_recommendations', 'dataset_practice_attempts']:
            db.query(f'ALTER TABLE {table} MODIFY created_at DATETIME(6) NOT NULL, MODIFY updated_at DATETIME(6) NOT NULL')
        db.query('ALTER TABLE dataset_questions ADD INDEX ix_bank_browse (usable_for_practice,usable_for_auto_grade,has_answer,subject,id,grade_band,dataset_source_id)')
        db.query('ALTER TABLE dataset_questions ADD INDEX ix_bank_grade (usable_for_practice,usable_for_auto_grade,has_answer,grade,subject,id)')
        db.query('CREATE TABLE cangjie_schema_versions (version VARCHAR(100) PRIMARY KEY, applied_at DATETIME NOT NULL) ENGINE=InnoDB')
        versions = ['001_initial', '002_work_precision', '003_diagnosis_precision', '004_tutor_precision', '005_practice_precision', '006_learning_tasks', '007_self_checks', '008_task_handwriting', '009_task_sources', '010_study_sessions', '011_bank_browse_index', '012_personal_learning', '013_bank_grade_index']
        for version in versions:
            db.query('INSERT INTO cangjie_schema_versions VALUES (?, UTC_TIMESTAMP())', [version])
