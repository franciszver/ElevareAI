-- Add password_hash Migration
-- AI Study Companion MVP
-- Version: 1.0.1

ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
