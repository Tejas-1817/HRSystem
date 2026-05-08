import io
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime

def generate_timesheet_excel(employee_name, timesheets):
    """
    Generates a professional Excel workbook for timesheet data.
    """
    wb = Workbook()
    
    # --- Style Definitions ---
    header_font = Font(name='Segoe UI', bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    center_aligned = Alignment(horizontal="center", vertical="center")
    border = Border(
        left=Side(style='thin'), 
        right=Side(style='thin'), 
        top=Side(style='thin'), 
        bottom=Side(style='thin')
    )
    
    # 1. Main Data Sheet
    ws = wb.active
    ws.title = "Timesheet Data"
    
    headers = [
        "Employee Name", "Project Name", "Task", "Description", 
        "Date", "Hours Worked", "Billable Status"
    ]
    
    # Add Headers
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_aligned
        cell.border = border

    # Add Data Rows
    total_hours = 0
    project_hours = {}
    billable_hours = {"Billable": 0, "Non-Billable": 0}

    for row_num, ts in enumerate(timesheets, 2):
        project = ts.get("project", "N/A")
        hours = float(ts.get("hours", 0))
        is_billable = "Billable" if ts.get("is_billable") else "Non-Billable"
        
        row_data = [
            ts.get("employee_name", employee_name),
            project,
            ts.get("task", "N/A"),
            ts.get("description", ""),
            ts.get("start_date").isoformat() if hasattr(ts.get("start_date"), "isoformat") else str(ts.get("start_date")),
            hours,
            is_billable
        ]
        
        for col_num, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_num, column=col_num, value=value)
            cell.border = border
            if col_num == 6:  # Hours column
                cell.alignment = Alignment(horizontal="right")
        
        # Aggregation for summary
        total_hours += hours
        project_hours[project] = project_hours.get(project, 0) + hours
        billable_hours[is_billable] += hours

    # Auto-adjust column widths
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column].width = adjusted_width

    # 2. Summary Sheet
    summary_ws = wb.create_sheet(title="Summary")
    summary_ws.append(["Summary Category", "Value"])
    
    # Style Summary Header
    for cell in summary_ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.border = border
    
    summary_ws.append(["Total Employees", 1])
    summary_ws.append(["Grand Total Hours", total_hours])
    summary_ws.append([])
    
    summary_ws.append(["Project Breakdown", "Hours"])
    for proj, hrs in project_hours.items():
        summary_ws.append([proj, hrs])
        
    summary_ws.append([])
    summary_ws.append(["Billability Breakdown", "Hours"])
    for status, hrs in billable_hours.items():
        summary_ws.append([status, hrs])

    # Finalize
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
