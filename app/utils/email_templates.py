"""
email_templates.py
==================
Centralized HTML email template factory for HRMS notifications.

Design:
  - Inline CSS for maximum email client compatibility (Gmail, Outlook, Apple Mail)
  - Mobile-responsive single-column layout (max-width: 600px)
  - Corporate Altzor HRMS branding (navy #1F4E78 / slate #2C3E50)
  - Every function returns (subject, html_body, plain_text_body)

Future-ready:
  - Swap render logic for Jinja2 templates with no API changes
  - Add company logo URL via Config.COMPANY_LOGO_URL
"""

from datetime import datetime


# ─── Brand Tokens ────────────────────────────────────────────────────────────
_COLOR_BRAND_PRIMARY   = "#1F4E78"   # Navy — header background
_COLOR_BRAND_SECONDARY = "#2C3E50"   # Dark Slate — secondary text
_COLOR_ACCENT_GREEN    = "#27AE60"   # Approved badge
_COLOR_ACCENT_RED      = "#E74C3C"   # Rejected badge
_COLOR_ACCENT_ORANGE   = "#F39C12"   # Pending badge
_COLOR_BG_PAGE         = "#F4F6F9"   # Page background
_COLOR_BG_CARD         = "#FFFFFF"   # Card/panel background
_COLOR_TEXT_BODY       = "#333333"   # Main body text
_COLOR_TEXT_MUTED      = "#777777"   # Footer / secondary
_COLOR_BORDER          = "#E0E0E0"   # Divider lines
_FONT_FAMILY           = "Segoe UI, Helvetica Neue, Arial, sans-serif"
_HRMS_NAME             = "RISE"


def _get_hrms_url() -> str:
    """Resolve the HRMS frontend URL from Config at call time (not import time)."""
    try:
        from app.config import Config
        return Config.FRONTEND_URL
    except Exception:
        return "http://localhost:5002"


# Module-level alias — used as f-string variable in templates.
# Each template function should call _get_hrms_url() to get the current value.
_HRMS_URL              = None  # Sentinel; see _get_hrms_url()


# ─── Internal Helpers ─────────────────────────────────────────────────────────

def _base_layout(header_title: str, header_subtitle: str, header_color: str, body_content: str) -> str:
    """
    Wraps content inside the standard Altzor HRMS email shell:
    - Full-width brand header
    - White card body
    - Corporate footer
    """
    year = datetime.now().year
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{header_title}</title>
</head>
<body style="margin:0;padding:0;background-color:{_COLOR_BG_PAGE};font-family:{_FONT_FAMILY};">

  <!-- Outer wrapper -->
  <table width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background-color:{_COLOR_BG_PAGE};padding:24px 0;">
    <tr>
      <td align="center">

        <!-- Email card -->
        <table width="600" cellpadding="0" cellspacing="0" border="0"
               style="max-width:600px;width:100%;border-radius:8px;
                      overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.10);">

          <!-- ── Brand Header ─────────────────────────────────────────── -->
          <tr>
            <td style="background-color:{header_color};padding:28px 32px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td>
                    <p style="margin:0;font-size:13px;font-weight:600;
                               color:rgba(255,255,255,0.75);letter-spacing:1.5px;
                               text-transform:uppercase;">{_HRMS_NAME}</p>
                    <h1 style="margin:6px 0 0;font-size:22px;font-weight:700;
                                color:#FFFFFF;line-height:1.3;">{header_title}</h1>
                    <p style="margin:6px 0 0;font-size:14px;color:rgba(255,255,255,0.85);">
                      {header_subtitle}
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- ── Body Card ────────────────────────────────────────────── -->
          <tr>
            <td style="background-color:{_COLOR_BG_CARD};padding:32px;">
              {body_content}
            </td>
          </tr>

          <!-- ── Footer ───────────────────────────────────────────────── -->
          <tr>
            <td style="background-color:#F8F9FB;padding:20px 32px;
                        border-top:1px solid {_COLOR_BORDER};">
              <p style="margin:0;font-size:12px;color:{_COLOR_TEXT_MUTED};line-height:1.6;">
                This is an automated notification from <strong>{_HRMS_NAME}</strong>.
                Please do not reply directly to this email.<br>
                <a href="{_get_hrms_url()}" style="color:{_COLOR_BRAND_PRIMARY};text-decoration:none;">
                  Open HRMS Dashboard
                </a>
                &nbsp;|&nbsp;
                &copy; {year} Altzor Technologies. All rights reserved.
              </p>
            </td>
          </tr>

        </table>
        <!-- /Email card -->

      </td>
    </tr>
  </table>

</body>
</html>"""


def _info_row(label: str, value: str) -> str:
    """Renders a single label-value row inside the details table."""
    return f"""
      <tr>
        <td style="padding:10px 16px;background-color:#F8F9FB;
                   border-bottom:1px solid {_COLOR_BORDER};
                   font-size:13px;font-weight:600;color:{_COLOR_BRAND_SECONDARY};
                   white-space:nowrap;width:38%;">{label}</td>
        <td style="padding:10px 16px;background-color:{_COLOR_BG_CARD};
                   border-bottom:1px solid {_COLOR_BORDER};
                   font-size:13px;color:{_COLOR_TEXT_BODY};">{value}</td>
      </tr>"""


def _details_table(*rows: str) -> str:
    """Wraps a set of _info_row() calls in a styled table."""
    content = "".join(rows)
    return f"""
      <table width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid {_COLOR_BORDER};border-radius:6px;
                    overflow:hidden;margin:20px 0;">
        {content}
      </table>"""


def _status_badge(label: str, color: str) -> str:
    return (f'<span style="display:inline-block;padding:4px 14px;'
            f'background-color:{color};color:#fff;border-radius:20px;'
            f'font-size:12px;font-weight:700;letter-spacing:0.5px;">'
            f'{label}</span>')


def _cta_button(text: str, url: str) -> str:
    return f"""
      <table cellpadding="0" cellspacing="0" border="0" style="margin:24px 0;">
        <tr>
          <td style="border-radius:6px;background-color:{_COLOR_BRAND_PRIMARY};">
            <a href="{url}" target="_blank"
               style="display:inline-block;padding:12px 28px;font-size:14px;
                      font-weight:600;color:#FFFFFF;text-decoration:none;
                      border-radius:6px;letter-spacing:0.3px;">{text}</a>
          </td>
        </tr>
      </table>"""


def _leave_type_label(leave_type: str) -> str:
    """Convert DB leave type code to human-readable label."""
    labels = {
        "sick":   "Sick Leave",
        "casual": "Casual Leave",
        "earned": "Earned / Privilege Leave",
    }
    return labels.get(leave_type.lower(), leave_type.title())


def _period_label(category: str, period: str | None) -> str:
    if category == "half_day":
        mapping = {"first_half": "First Half (Morning)", "second_half": "Second Half (Afternoon)"}
        return mapping.get(period or "", "Half Day")
    return "Full Day"


# ─── Public Template Functions ────────────────────────────────────────────────

def leave_application_to_manager(
    manager_name: str,
    employee_name: str,
    employee_id: str | None,
    leave_type: str,
    leave_type_category: str,
    half_day_period: str | None,
    start_date: str,
    end_date: str,
    total_days: float,
    reason: str,
    submitted_at: str,
    leave_id: int | None = None,
) -> tuple[str, str, str]:
    """
    Email sent to the Manager when a Team Member submits a leave request.

    Returns:
        (subject, html_body, plain_text_body)
    """
    subject = f"New Leave Request Submitted – {employee_name}"
    leave_type_label = _leave_type_label(leave_type)
    period_str = _period_label(leave_type_category, half_day_period)
    review_url = f"{_get_hrms_url()}/leaves" + (f"/{leave_id}" if leave_id else "")
    emp_id_display = str(employee_id) if employee_id else "N/A"
    duration_display = f"{total_days:.1f} day(s) ({period_str})"

    body_content = f"""
      <p style="margin:0 0 4px;font-size:15px;color:{_COLOR_TEXT_BODY};line-height:1.6;">
        Dear <strong>{manager_name}</strong>,
      </p>
      <p style="margin:8px 0 20px;font-size:15px;color:{_COLOR_TEXT_BODY};line-height:1.6;">
        A new leave request has been submitted and requires your review.
      </p>

      {_details_table(
          _info_row("Team Member", f"<strong>{employee_name}</strong>"),
          _info_row("Team Member ID", emp_id_display),
          _info_row("Leave Type", leave_type_label),
          _info_row("Duration", duration_display),
          _info_row("From Date", f"<strong>{start_date}</strong>"),
          _info_row("To Date", f"<strong>{end_date}</strong>"),
          _info_row("Total Days Requested", f"<strong>{total_days:.1f}</strong>"),
          _info_row("Reason", reason or "<em style='color:#999;'>No reason provided</em>"),
          _info_row("Submitted At", submitted_at),
          _info_row("Status", _status_badge("PENDING APPROVAL", _COLOR_ACCENT_ORANGE)),
      )}

      <p style="margin:16px 0 8px;font-size:14px;color:{_COLOR_TEXT_BODY};">
        Please log in to the HRMS to approve or reject this request.
      </p>

      {_cta_button("Review Leave Request →", review_url)}

      <p style="margin:20px 0 0;font-size:13px;color:{_COLOR_TEXT_MUTED};
                border-top:1px solid {_COLOR_BORDER};padding-top:16px;">
        If you believe this leave was submitted in error or requires clarification,
        please contact the team member or HR directly.
      </p>
    """

    html_body = _base_layout(
        header_title="New Leave Request",
        header_subtitle=f"Submitted by {employee_name} · Awaiting your review",
        header_color=_COLOR_BRAND_PRIMARY,
        body_content=body_content,
    )

    plain_text_body = f"""New Leave Request — {_HRMS_NAME}

Dear {manager_name},

A new leave request has been submitted by {employee_name} and requires your review.

Team Member   : {employee_name}
Team Member ID: {emp_id_display}
Leave Type    : {leave_type_label}
Duration      : {duration_display}
From Date     : {start_date}
To Date       : {end_date}
Total Days    : {total_days:.1f}
Reason        : {reason or 'No reason provided'}
Submitted At  : {submitted_at}
Status        : PENDING APPROVAL

Please log in to the HRMS to review this request:
{review_url}

---
This is an automated message from {_HRMS_NAME}.
"""

    return subject, html_body, plain_text_body


def leave_approved_to_employee(
    employee_name: str,
    approved_by: str,
    leave_type: str,
    leave_type_category: str,
    half_day_period: str | None,
    start_date: str,
    end_date: str,
    total_days: float,
    approved_at: str,
    leave_id: int | None = None,
) -> tuple[str, str, str]:
    """
    Email sent to the Team Member when their leave is approved.

    Returns:
        (subject, html_body, plain_text_body)
    """
    subject = f"Your Leave Request Has Been Approved – {_HRMS_NAME}"
    leave_type_label = _leave_type_label(leave_type)
    period_str = _period_label(leave_type_category, half_day_period)
    duration_display = f"{total_days:.1f} day(s) ({period_str})"

    body_content = f"""
      <p style="margin:0 0 4px;font-size:15px;color:{_COLOR_TEXT_BODY};line-height:1.6;">
        Dear <strong>{employee_name}</strong>,
      </p>
      <p style="margin:8px 0 20px;font-size:15px;color:{_COLOR_TEXT_BODY};line-height:1.6;">
        Great news! Your leave request has been <strong style="color:{_COLOR_ACCENT_GREEN};">approved</strong>.
      </p>

      {_details_table(
          _info_row("Leave Type", leave_type_label),
          _info_row("Duration", duration_display),
          _info_row("From Date", f"<strong>{start_date}</strong>"),
          _info_row("To Date", f"<strong>{end_date}</strong>"),
          _info_row("Total Days", f"<strong>{total_days:.1f}</strong>"),
          _info_row("Approved By", approved_by),
          _info_row("Approved At", approved_at),
          _info_row("Status", _status_badge("APPROVED", _COLOR_ACCENT_GREEN)),
      )}

      <p style="margin:16px 0 8px;font-size:14px;color:{_COLOR_TEXT_BODY};">
        Your leave balance has been updated accordingly. You can view your updated
        balance in the HRMS portal.
      </p>

      {_cta_button("View My Leave Balance →", f"{_get_hrms_url()}/leaves/balance")}

      <p style="margin:20px 0 0;font-size:13px;color:{_COLOR_TEXT_MUTED};
                border-top:1px solid {_COLOR_BORDER};padding-top:16px;">
        If you have any questions, please contact your manager or HR.
      </p>
    """

    html_body = _base_layout(
        header_title="Leave Approved ✓",
        header_subtitle=f"Your {leave_type_label} request has been approved",
        header_color=_COLOR_ACCENT_GREEN,
        body_content=body_content,
    )

    plain_text_body = f"""Leave Approved — {_HRMS_NAME}

Dear {employee_name},

Your leave request has been APPROVED.

Leave Type  : {leave_type_label}
Duration    : {duration_display}
From Date   : {start_date}
To Date     : {end_date}
Total Days  : {total_days:.1f}
Approved By : {approved_by}
Approved At : {approved_at}

Your leave balance has been updated. Log in to view it:
{_get_hrms_url()}/leaves/balance

---
This is an automated message from {_HRMS_NAME}.
"""

    return subject, html_body, plain_text_body


def leave_rejected_to_employee(
    employee_name: str,
    rejected_by: str,
    leave_type: str,
    leave_type_category: str,
    half_day_period: str | None,
    start_date: str,
    end_date: str,
    total_days: float,
    rejection_reason: str,
    rejected_at: str,
    leave_id: int | None = None,
) -> tuple[str, str, str]:
    """
    Email sent to the Team Member when their leave is rejected.

    Returns:
        (subject, html_body, plain_text_body)
    """
    subject = f"Your Leave Request Has Been Rejected – {_HRMS_NAME}"
    leave_type_label = _leave_type_label(leave_type)
    period_str = _period_label(leave_type_category, half_day_period)
    duration_display = f"{total_days:.1f} day(s) ({period_str})"

    body_content = f"""
      <p style="margin:0 0 4px;font-size:15px;color:{_COLOR_TEXT_BODY};line-height:1.6;">
        Dear <strong>{employee_name}</strong>,
      </p>
      <p style="margin:8px 0 20px;font-size:15px;color:{_COLOR_TEXT_BODY};line-height:1.6;">
        We regret to inform you that your leave request has been
        <strong style="color:{_COLOR_ACCENT_RED};">rejected</strong>.
        Please review the details and reason below.
      </p>

      {_details_table(
          _info_row("Leave Type", leave_type_label),
          _info_row("Duration", duration_display),
          _info_row("From Date", f"<strong>{start_date}</strong>"),
          _info_row("To Date", f"<strong>{end_date}</strong>"),
          _info_row("Total Days", f"<strong>{total_days:.1f}</strong>"),
          _info_row("Rejected By", rejected_by),
          _info_row("Rejected At", rejected_at),
          _info_row("Status", _status_badge("REJECTED", _COLOR_ACCENT_RED)),
          _info_row("Rejection Reason",
                    f'<span style="color:{_COLOR_ACCENT_RED};font-weight:600;">'
                    f'{rejection_reason or "No reason provided"}</span>'),
      )}

      <p style="margin:16px 0 8px;font-size:14px;color:{_COLOR_TEXT_BODY};">
        If you have concerns about this decision, please speak with your manager
        or raise a query through the HRMS helpdesk.
      </p>

      {_cta_button("Apply for New Leave →", f"{_get_hrms_url()}/leaves/apply")}

      <p style="margin:20px 0 0;font-size:13px;color:{_COLOR_TEXT_MUTED};
                border-top:1px solid {_COLOR_BORDER};padding-top:16px;">
        Your leave balance has <strong>not</strong> been deducted for this request.
      </p>
    """

    html_body = _base_layout(
        header_title="Leave Request Rejected",
        header_subtitle=f"Your {leave_type_label} request could not be approved",
        header_color=_COLOR_ACCENT_RED,
        body_content=body_content,
    )

    plain_text_body = f"""Leave Rejected — {_HRMS_NAME}

Dear {employee_name},

Your leave request has been REJECTED.

Leave Type       : {leave_type_label}
Duration         : {duration_display}
From Date        : {start_date}
To Date          : {end_date}
Total Days       : {total_days:.1f}
Rejected By      : {rejected_by}
Rejected At      : {rejected_at}
Rejection Reason : {rejection_reason or 'No reason provided'}

Your leave balance has NOT been deducted for this request.

If you have concerns, please contact your manager or HR.
Log in to the HRMS: {_get_hrms_url()}

---
This is an automated message from {_HRMS_NAME}.
"""

    return subject, html_body, plain_text_body
