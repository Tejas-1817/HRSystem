"""
Altzor Digital Solutions Pvt. Ltd. — Device Usage Agreement Template.

This module provides the full agreement text matching the company PDF.
Placeholders are filled at runtime with device and employee details.
"""

AGREEMENT_VERSION = "1.0"

AGREEMENT_TEMPLATE = """
ALTZOR DIGITAL SOLUTIONS PVT. LTD.
DEVICE USAGE AGREEMENT
Version {agreement_version}

Date of Issue: {assigned_date}

Employee Name: {employee_name}
Employee ID: {employee_id}
Device: {brand} {model}
Serial Number: {serial_number}
Device Type: {device_type}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. General Guidelines

   • Users must ensure proper care, handling, and safe usage of the device at all times.
   • Confidentiality of company data must be maintained without exception.
   • The device is the property of Altzor Digital Solutions Pvt. Ltd. and must be returned upon request or termination of employment.
   • The device must be used primarily for official work purposes.

2. Security Responsibilities

   • Users are responsible for protecting data stored on the device.
   • Passwords must be strong and changed periodically (every 90 days).
   • The device must be locked when unattended.
   • Any loss, theft, or security incident must be reported immediately.

3. System Handling & Maintenance

   • The Laptop/MacBook must be kept clean and stored in a safe, dry environment.
   • Only authorized personnel may install or modify software.
   • Regular updates and system patches must not be ignored.

4. Restrictions

   • Personal, commercial, or unauthorized use is strictly prohibited.
   • External storage devices must not be used to store company data.
   • Accessing unsecured/public Wi-Fi networks is not allowed.
   • Installation of unauthorized or pirated software is prohibited.
   • The device must not be shared with unauthorized individuals.

5. Liability & Compliance

   • The user will be held accountable for any damage or loss due to negligence.
   • In case of theft, a police complaint must be filed and submitted to the company.
   • Any policy violations may result in disciplinary or legal action.

6. Additional Security Measures

   • The user is responsible for protecting the Laptop/MacBook physically.
   • Any configuration change or software installation requires prior approval from the authorized manager.
   • The user is responsible for maintaining all required security protocols.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DECLARATION

I have read, understood, and agree to abide by all the terms and conditions
stated in this document and the annexed policy.

Employee Name: {employee_name}
Employee ID: {employee_id}
Company: Altzor Pvt. Ltd.
Date: {assigned_date}

E-Mail: support@altzor.com
Website: www.altzor.com
"""


def render_agreement(employee_name: str, employee_id, device: dict, assigned_date: str) -> str:
    """
    Fill the agreement template with actual device and employee details.

    Parameters
    ----------
    employee_name : str
        The system name of the employee (e.g. T_Kartik).
    employee_id : int | str
        The employee table ID.
    device : dict
        Row from the `devices` table (must have brand, model, serial_number, device_type).
    assigned_date : str
        Date the device was assigned (YYYY-MM-DD).

    Returns
    -------
    str
        The fully rendered agreement text.
    """
    return AGREEMENT_TEMPLATE.format(
        agreement_version=AGREEMENT_VERSION,
        employee_name=employee_name,
        employee_id=employee_id,
        brand=device.get("brand", ""),
        model=device.get("model", ""),
        serial_number=device.get("serial_number", ""),
        device_type=device.get("device_type", "Laptop"),
        assigned_date=assigned_date,
    )
