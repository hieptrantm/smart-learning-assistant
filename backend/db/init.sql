DROP TABLE IF EXISTS detects CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- CREATE TABLE users (
--   id SERIAL PRIMARY KEY,
--   username VARCHAR(50) UNIQUE NOT NULL,
--   email VARCHAR(100) UNIQUE NOT NULL,
--   password_hash TEXT,
--   email_verified BOOLEAN DEFAULT FALSE,
--   provider VARCHAR(50) NOT NULL,
--   provider_id VARCHAR(100),
--   last_login TIMESTAMP,
--   created_at TIMESTAMP DEFAULT NOW(),
--   UNIQUE (provider, provider_id)
-- );

CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  username VARCHAR(50) UNIQUE NOT NULL,
  email VARCHAR(100) UNIQUE NOT NULL,
  password_hash TEXT,
  email_verified BOOLEAN DEFAULT FALSE,
  last_login TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE auth_providers (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider VARCHAR(50) NOT NULL,
  provider_id VARCHAR(100),
  UNIQUE (provider, provider_id),
  UNIQUE (user_id, provider)
);


-- ============================================================
-- STUDY PLANNER TABLES
-- ============================================================

CREATE TABLE study_subjects (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name VARCHAR(200) NOT NULL,
  emoji VARCHAR(10) DEFAULT '📚',
  target_grade NUMERIC(3,1) DEFAULT 7.0,
  end_date DATE,
  status VARCHAR(30) DEFAULT 'active',  -- active / completed / archived
  ingest_job_id VARCHAR(200),           -- job ID from data-ingestor
  ingest_status VARCHAR(30) DEFAULT 'pending', -- pending / processing / completed / failed
  plan_status VARCHAR(30) DEFAULT 'pending',   -- pending / generating / completed / failed
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE subject_documents (
  id SERIAL PRIMARY KEY,
  subject_id INT NOT NULL REFERENCES study_subjects(id) ON DELETE CASCADE,
  file_name VARCHAR(500) NOT NULL,
  file_size VARCHAR(50),
  mime_type VARCHAR(100),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE subject_free_slots (
  id SERIAL PRIMARY KEY,
  subject_id INT NOT NULL REFERENCES study_subjects(id) ON DELETE CASCADE,
  day_of_week VARCHAR(10) NOT NULL,  -- mon, tue, wed, thu, fri, sat, sun
  time_slot VARCHAR(10) NOT NULL,    -- e.g. "08:00"
  UNIQUE(subject_id, day_of_week, time_slot)
);

CREATE TABLE study_plans (
  id SERIAL PRIMARY KEY,
  subject_id INT NOT NULL REFERENCES study_subjects(id) ON DELETE CASCADE,
  plan_json JSONB NOT NULL,           -- full generated plan
  calendar_synced BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE study_sessions (
  id SERIAL PRIMARY KEY,
  plan_id INT NOT NULL REFERENCES study_plans(id) ON DELETE CASCADE,
  subject_id INT NOT NULL REFERENCES study_subjects(id) ON DELETE CASCADE,
  session_date DATE NOT NULL,
  start_time VARCHAR(10) NOT NULL,
  end_time VARCHAR(10) NOT NULL,
  title VARCHAR(500),
  content TEXT,
  calendar_event_id VARCHAR(200),   
  status VARCHAR(30) DEFAULT 'scheduled',
  learning_status VARCHAR(30) DEFAULT 'not_started', -- not_started / passed / failed
  checkpoint_node_id VARCHAR(200),
  score NUMERIC(5,2),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE subject_messages (
  id SERIAL PRIMARY KEY,
  subject_id INT NOT NULL REFERENCES study_subjects(id) ON DELETE CASCADE,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role VARCHAR(20) NOT NULL,          -- 'user' or 'assistant'
  content TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);