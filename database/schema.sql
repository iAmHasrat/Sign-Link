CREATE DATABASE IF NOT EXISTS sign_link CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE sign_link;

CREATE TABLE IF NOT EXISTS users (
  user_id INT AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(120) NOT NULL,
  username VARCHAR(30) NOT NULL UNIQUE,
  email VARCHAR(180) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('Deaf', 'Hearing') NOT NULL,
  preferred_language ENUM('en', 'hi', 'pa') NOT NULL DEFAULT 'en',
  profile_picture VARCHAR(500),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_users_search (full_name, username, email)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS calls (
  call_id INT AUTO_INCREMENT PRIMARY KEY,
  caller_id INT NOT NULL,
  receiver_id INT NOT NULL,
  start_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  end_time TIMESTAMP NULL,
  duration_seconds INT DEFAULT 0,
  call_status ENUM('started', 'completed', 'rejected', 'missed', 'failed') NOT NULL DEFAULT 'started',
  CONSTRAINT fk_calls_caller FOREIGN KEY (caller_id) REFERENCES users(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_calls_receiver FOREIGN KEY (receiver_id) REFERENCES users(user_id) ON DELETE CASCADE,
  INDEX idx_calls_user_time (caller_id, receiver_id, start_time)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS messages (
  message_id INT AUTO_INCREMENT PRIMARY KEY,
  sender_id INT NOT NULL,
  receiver_id INT NOT NULL,
  message_text TEXT NOT NULL,
  seen_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_messages_sender FOREIGN KEY (sender_id) REFERENCES users(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_messages_receiver FOREIGN KEY (receiver_id) REFERENCES users(user_id) ON DELETE CASCADE,
  INDEX idx_messages_conversation (sender_id, receiver_id, created_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS call_history (
  history_id INT AUTO_INCREMENT PRIMARY KEY,
  call_id INT NOT NULL,
  caller_id INT NOT NULL,
  receiver_id INT NOT NULL,
  CONSTRAINT fk_history_call FOREIGN KEY (call_id) REFERENCES calls(call_id) ON DELETE CASCADE,
  CONSTRAINT fk_history_caller FOREIGN KEY (caller_id) REFERENCES users(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_history_receiver FOREIGN KEY (receiver_id) REFERENCES users(user_id) ON DELETE CASCADE,
  INDEX idx_history_user (caller_id, receiver_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS translations (
  translation_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  source_text TEXT NOT NULL,
  translated_text TEXT NOT NULL,
  target_language ENUM('en', 'hi', 'pa') NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_translations_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  INDEX idx_translations_user_time (user_id, created_at)
) ENGINE=InnoDB;
