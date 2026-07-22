-- Migration 024: Add superadmin role to users table ENUM

ALTER TABLE users
  MODIFY COLUMN role ENUM(
    'admin','hr','manager','employee','team_member',
    'onboarding_candidate','superadmin'
  ) NOT NULL DEFAULT 'employee';
