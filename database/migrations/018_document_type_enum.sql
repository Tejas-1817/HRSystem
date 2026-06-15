-- ═══════════════════════════════════════════════════════════════════════════
-- Migration 018: Update onboarding_documents ENUM for Document Management API
-- ═══════════════════════════════════════════════════════════════════════════
--
-- Purpose:
--   Extend the document_type ENUM on onboarding_documents to include all
--   document types required by the Enterprise Document Management API:
--     AADHAR, PAN, PASSPORT, DEGREE_CERTIFICATE, EXPERIENCE_LETTER,
--     OFFER_LETTER, BANK_PASSBOOK, PHOTO, OTHER
--
--   Also preserves the original values (PASSPORT_COPY, ACADEMIC_CERTIFICATE,
--   RELIEVING_LETTER, PAY_SLIP, APPRAISAL_LETTER, DRIVING_LICENSE_VOTER_ID)
--   for backward compatibility with any existing records.
--
-- Safety: MODIFY COLUMN is idempotent — running it multiple times is safe.
-- ═══════════════════════════════════════════════════════════════════════════

USE hrms;

ALTER TABLE onboarding_documents
    MODIFY COLUMN document_type ENUM(
        'AADHAR',
        'PAN',
        'PASSPORT',
        'PASSPORT_COPY',
        'DEGREE_CERTIFICATE',
        'ACADEMIC_CERTIFICATE',
        'EXPERIENCE_LETTER',
        'OFFER_LETTER',
        'RELIEVING_LETTER',
        'PAY_SLIP',
        'APPRAISAL_LETTER',
        'BANK_PASSBOOK',
        'DRIVING_LICENSE_VOTER_ID',
        'PHOTO',
        'OTHER'
    ) NOT NULL;
