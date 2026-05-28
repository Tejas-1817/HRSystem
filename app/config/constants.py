"""
Centralized Constants Configuration
────────────────────────────────────
Single source of truth for all dropdown values, validation constants,
and enterprise HR field options used across the HRMS system.

This module avoids hardcoded values in routes/services and supports
easy extension without code changes across multiple files.

Usage:
    from app.config.constants import (
        DEPARTMENTS, DESIGNATIONS, GENDERS,
        EMPLOYMENT_TYPES, is_valid_department,
        is_valid_gender, is_valid_employment_type,
    )
"""

import logging

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════
# DEPARTMENT OPTIONS (Default set — can be extended via dynamic management)
# ═════════════════════════════════════════════════════════════════════════
DEPARTMENTS = (
    "Engineering",
    "HR",
    "Finance",
    "Recruitment",
    "Operations",
    "Marketing",
    "Sales",
    "Legal",
    "IT",
    "Administration",
    "Product",
    "Design",
    "Quality Assurance",
    "Customer Support",
    "Research & Development",
)

# ═════════════════════════════════════════════════════════════════════════
# DESIGNATION OPTIONS (Default set — can be extended via dynamic management)
# ═════════════════════════════════════════════════════════════════════════
DESIGNATIONS = (
    "Software Engineer",
    "Senior Software Engineer",
    "HR Executive",
    "HR Manager",
    "Project Manager",
    "Recruiter",
    "Senior Developer",
    "Team Lead",
    "QA Engineer",
    "DevOps Engineer",
    "Business Analyst",
    "Product Manager",
    "Technical Lead",
    "Data Analyst",
    "UI/UX Designer",
    "System Administrator",
    "Intern",
    "Trainee",
)

# ═════════════════════════════════════════════════════════════════════════
# GENDER OPTIONS
# ═════════════════════════════════════════════════════════════════════════
GENDERS = (
    "Male",
    "Female",
    "Other",
    "Prefer Not to Say",
)

# ═════════════════════════════════════════════════════════════════════════
# EMPLOYMENT TYPE OPTIONS
# ═════════════════════════════════════════════════════════════════════════
EMPLOYMENT_TYPES = (
    "Full Time",
    "Intern",
    "Contract Based",
    "Part Time",
    "Freelancer",
    "Temporary",
)

# ═════════════════════════════════════════════════════════════════════════
# TEAM MEMBER CODE FORMAT
# ═════════════════════════════════════════════════════════════════════════
TEAM_MEMBER_CODE_PREFIX = "TM"
TEAM_MEMBER_CODE_FORMAT = "{prefix}-{year}-{number:04d}"  # TM-2026-0001

# ═════════════════════════════════════════════════════════════════════════
# VALIDATION CONSTANTS
# ═════════════════════════════════════════════════════════════════════════
MAX_DESIGNATION_LENGTH = 100
MAX_DEPARTMENT_LENGTH = 100
MAX_GENDER_LENGTH = 30
MAX_EMPLOYMENT_TYPE_LENGTH = 50
MAX_ADDRESS_LENGTH = 500
MAX_TEAM_MEMBER_CODE_LENGTH = 20


# ═════════════════════════════════════════════════════════════════════════
# VALIDATION HELPERS
# ═════════════════════════════════════════════════════════════════════════

def is_valid_gender(value: str) -> bool:
    """Validate gender selection against allowed values."""
    if not value:
        return True  # Gender is optional
    return value.strip() in GENDERS


def is_valid_employment_type(value: str) -> bool:
    """Validate employment type against allowed values."""
    if not value:
        return True  # Employment type is optional
    return value.strip() in EMPLOYMENT_TYPES


def is_valid_department(value: str, include_dynamic: bool = True) -> bool:
    """
    Validate department against static defaults.
    
    When include_dynamic is True, this only validates against
    the static list. Dynamic departments from the database are
    validated at the service layer.
    """
    if not value:
        return True  # Department is optional
    return value.strip() in DEPARTMENTS


def is_valid_designation(value: str) -> bool:
    """
    Validate designation against static defaults.
    Dynamic designations from the database are validated at the service layer.
    """
    if not value:
        return True  # Designation is optional
    return value.strip() in DESIGNATIONS


def get_departments_list() -> list:
    """Return departments as a list (for API response)."""
    return list(DEPARTMENTS)


def get_designations_list() -> list:
    """Return designations as a list (for API response)."""
    return list(DESIGNATIONS)


def get_genders_list() -> list:
    """Return genders as a list (for API response)."""
    return list(GENDERS)


def get_employment_types_list() -> list:
    """Return employment types as a list (for API response)."""
    return list(EMPLOYMENT_TYPES)


# ═════════════════════════════════════════════════════════════════════════
# STARTUP LOGGING
# ═════════════════════════════════════════════════════════════════════════
logger.info(
    "[Constants] Loaded → Departments=%d, Designations=%d, "
    "Genders=%d, EmploymentTypes=%d",
    len(DEPARTMENTS), len(DESIGNATIONS),
    len(GENDERS), len(EMPLOYMENT_TYPES),
)
