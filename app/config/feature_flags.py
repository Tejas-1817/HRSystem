"""
Feature Flags — Centralized Feature Toggle Configuration

Provides a single control point for enabling or disabling HRMS features.
Each flag can be overridden at runtime via environment variables so that
no code deployment is required to change system behaviour.

Usage:
    from app.config.feature_flags import FeatureFlags

    if not FeatureFlags.BANK_DETAILS_EDITABLE:
        # block mutation ...

Future flags follow the same pattern — add to FeatureFlags, wire env var,
document below. Never hard-code feature state inside route handlers.
"""

import os
import logging

logger = logging.getLogger(__name__)


class FeatureFlags:
    """
    Enterprise feature-flag registry.

    Each attribute maps directly to an environment variable of the same name.
    Default values represent the safe / locked production state.

    ┌─────────────────────────────┬───────────┬──────────────────────────────────────┐
    │ Flag                        │ Default   │ Purpose                              │
    ├─────────────────────────────┼───────────┼──────────────────────────────────────┤
    │ BANK_DETAILS_EDITABLE       │ False     │ Allow / block bank detail mutations  │
    └─────────────────────────────┴───────────┴──────────────────────────────────────┘

    To unlock bank editing without a code change:
        Set environment variable:  BANK_DETAILS_EDITABLE=true
        Then restart the application server.
    """

    # ─────────────────────────────────────────────────────────────────────────
    # Bank Details Protection
    # ─────────────────────────────────────────────────────────────────────────
    BANK_DETAILS_EDITABLE: bool = (
        os.getenv("BANK_DETAILS_EDITABLE", "false").strip().lower() == "true"
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Future flags — add here, never inside route handlers
    # ─────────────────────────────────────────────────────────────────────────
    # SALARY_EDITABLE: bool = os.getenv("SALARY_EDITABLE", "true").strip().lower() == "true"
    # DOCUMENTS_UPLOAD_ENABLED: bool = os.getenv("DOCUMENTS_UPLOAD_ENABLED", "true") ...


# ─────────────────────────────────────────────────────────────────────────────
# Emit resolved flag values at import time so they appear in startup logs.
# This helps ops teams confirm which flags are active without grepping code.
# ─────────────────────────────────────────────────────────────────────────────
logger.info(
    "[FeatureFlags] Resolved → BANK_DETAILS_EDITABLE=%s",
    FeatureFlags.BANK_DETAILS_EDITABLE,
)
