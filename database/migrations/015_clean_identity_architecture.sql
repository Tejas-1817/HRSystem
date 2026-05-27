-- ═══════════════════════════════════════════════════════════════════════════
-- Migration 015: Clean Enterprise Identity Architecture
-- ═══════════════════════════════════════════════════════════════════════════
-- 
-- Purpose:
--   1. Drop redundant `original_name` columns from `employee` and `users`
--      since the primary `name` / `employee_name` will now permanently store
--      the clean name without any role prefixes.
--
-- Safety: 
--   Only run this AFTER executing run_015.py which performs the actual 
--   prefix stripping and cascade renaming.
-- ═══════════════════════════════════════════════════════════════════════════

USE hrms;

-- Drop original_name from employee table if it exists
ALTER TABLE employee DROP COLUMN IF EXISTS original_name;

-- Drop original_name from users table if it exists
ALTER TABLE users DROP COLUMN IF EXISTS original_name;
