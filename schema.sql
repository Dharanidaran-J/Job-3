-- ChallengeHire schema (MySQL 8+ / MariaDB 10.5+)
CREATE DATABASE IF NOT EXISTS challengehire CHARACTER SET utf8mb4;
USE challengehire;

CREATE TABLE IF NOT EXISTS companies (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL UNIQUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  role ENUM('student','recruiter') NOT NULL,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(190) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  college VARCHAR(150) NULL,
  company_id INT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (company_id) REFERENCES companies(id)
);
CREATE TABLE IF NOT EXISTS skills (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(50) NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS student_skills (
  user_id INT NOT NULL, skill_id INT NOT NULL,
  PRIMARY KEY (user_id, skill_id),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS jobs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  company_id INT NOT NULL,
  recruiter_id INT NOT NULL,
  title VARCHAR(150) NOT NULL,
  description TEXT NOT NULL,
  level VARCHAR(50) NOT NULL,
  type VARCHAR(30) NOT NULL,
  location VARCHAR(100) NOT NULL,
  salary VARCHAR(60) NULL,
  deadline DATE NOT NULL,
  is_open TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (company_id) REFERENCES companies(id),
  FOREIGN KEY (recruiter_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_jobs_recruiter (recruiter_id),
  INDEX idx_jobs_open (is_open, deadline)
);
CREATE TABLE IF NOT EXISTS job_skills (
  job_id INT NOT NULL, skill_id INT NOT NULL,
  PRIMARY KEY (job_id, skill_id),
  FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
  FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS challenges (
  id INT AUTO_INCREMENT PRIMARY KEY,
  recruiter_id INT NOT NULL,
  job_id INT NULL,
  title VARCHAR(150) NOT NULL,
  statement TEXT NOT NULL,
  difficulty ENUM('Easy','Medium','Hard') NOT NULL,
  max_score INT NOT NULL DEFAULT 100 CHECK (max_score > 0),
  criteria VARCHAR(500) NOT NULL,
  deadline DATE NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (recruiter_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL,
  INDEX idx_ch_recruiter (recruiter_id),
  INDEX idx_ch_job (job_id)
);
CREATE TABLE IF NOT EXISTS challenge_skills (
  challenge_id INT NOT NULL, skill_id INT NOT NULL,
  PRIMARY KEY (challenge_id, skill_id),
  FOREIGN KEY (challenge_id) REFERENCES challenges(id) ON DELETE CASCADE,
  FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS applications (
  id INT AUTO_INCREMENT PRIMARY KEY,
  job_id INT NOT NULL,
  student_id INT NOT NULL,
  status ENUM('Applied','Assessment Pending','Under Review','Shortlisted','Rejected','Selected') NOT NULL DEFAULT 'Applied',
  applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_application (job_id, student_id),
  FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
  FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS submissions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  challenge_id INT NOT NULL,
  student_id INT NOT NULL,
  link VARCHAR(500) NOT NULL,
  note VARCHAR(500) NOT NULL DEFAULT '',
  submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (challenge_id) REFERENCES challenges(id) ON DELETE CASCADE,
  FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_sub_student (student_id, challenge_id)
);
CREATE TABLE IF NOT EXISTS evaluation_results (
  id INT AUTO_INCREMENT PRIMARY KEY,
  submission_id INT NOT NULL UNIQUE,
  reviewer_id INT NOT NULL,
  score INT NOT NULL CHECK (score >= 0),
  feedback VARCHAR(1000) NOT NULL DEFAULT '',
  evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE,
  FOREIGN KEY (reviewer_id) REFERENCES users(id)
);
