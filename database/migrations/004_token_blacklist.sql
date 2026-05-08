-- Migration 004: Token Blacklist Table
-- Description: Stores invalidated JWT hashes to prevent reuse after logout.
-- Author: Senior Security Engineer

USE starterdata;

CREATE TABLE IF NOT EXISTS token_blacklist (
    id INT AUTO_INCREMENT PRIMARY KEY,
    token_hash VARCHAR(64) UNIQUE NOT NULL, -- SHA256 hash of the token
    expires_at DATETIME NOT NULL,           -- When the token would have naturally expired
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_token_expiry (expires_at)     -- For efficient cleanup
);
