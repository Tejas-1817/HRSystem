"""
Feature Flag Configuration
===========================
Centralized, enterprise-grade feature toggle management.

Controls which system capabilities are currently enabled or disabled
without requiring code deployments. Flip a flag here and the entire
backend enforces the change immediately.

Usage:
    from app.config.feature_flags import FeatureFlags, is_bank_editable

    if not is_bank_editable():
        # block the mutation
        ...

To re-enable bank-detail editing in the future, set:
    BANK_DETAILS_EDITABLE = True
"""

import os
import logging

logger = logging.getLogger(__name__)


class FeatureFlags:
    """
    Global feature-flag registry.

    All flags here are the single source of truth for feature availability
    across the entire backend. No scattered if-statements in business logic
    — import from here and use the helper functions below.

    ─────────────────────────────────────────────────────────────────────
    BANK DETAILS PROTECTION
    ─────────────────────────────────────────────────────────────────────
    BANK_DETAILS_EDITABLE:
        False  → All create / update / delete operations on bank_details
                 are blocked for EVERY role (including admin/hr).
                 View (GET) endpoints remain fully functional.
        True   → Normal CRUD behaviour is restored.

    Compliance note: Set to False whenever an external audit, payroll
    freeze, or regulatory review is in progress. Any mutation attempt
    while False is logged to audit_logs automatically.
    """

    # ── Bank Details ───────────────────────────────────────────────────
    BANK_DETAILS_EDITABLE: bool = False  # <── MASTER SWITCH

    # ── (Reserved) Future feature flags ───────────────────────────────
    # SALARY_EDITABLE: bool = True
    # LEAVE_POLICY_EDITABLE: bool = True
    # TIMESHEET_EDITABLE: bool = True


# ---------------------------------------------------------------------------
# Public helper functions — import these in routes / services
# ---------------------------------------------------------------------------

def is_bank_editable() -> bool:
    """
    Returns True when bank-detail mutations are currently permitted.

    Also supports an environment-variable override so you can toggle
    the flag without a code change during hotfixes:

        HRMS_BANK_EDITABLE=true  →  override to True
        HRMS_BANK_EDITABLE=false →  override to False  (default)

    The env-var always wins over the class constant.
    """
    env_override = os.environ.get("HRMS_BANK_EDITABLE", "").strip().lower()
    if env_override in ("1", "true", "yes"):
        logger.debug("FeatureFlag: BANK_DETAILS_EDITABLE overridden to True via env var.")
        return True
    if env_override in ("0", "false", "no"):
        logger.debug("FeatureFlag: BANK_DETAILS_EDITABLE overridden to False via env var.")
        return False
    return FeatureFlags.BANK_DETAILS_EDITABLE


# Convenience constant for direct reads (refreshed at module load time only)
BANK_DETAILS_EDITABLE = FeatureFlags.BANK_DETAILS_EDITABLE
