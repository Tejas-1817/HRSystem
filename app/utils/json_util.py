
import json
from datetime import datetime, date, timedelta
from decimal import Decimal
from flask import jsonify

class HRMSJsonEncoder(json.JSONEncoder):
    """
    Custom JSON Encoder for HRMS to handle:
    - datetime / date → ISO format string
    - timedelta → string (HH:MM:SS)
    - Decimal → float
    """
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, timedelta):
            return str(obj)
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

def safe_jsonify(data, status=200):
    """
    Production-grade jsonify replacement that handles Decimals and Datetimes.
    Prevents 500 errors during JSON serialization.
    """
    try:
        # We use json.dumps with our custom encoder, then json.loads to get a dict/list
        # that Flask's jsonify can handle without crashing.
        serialized = json.dumps(data, cls=HRMSJsonEncoder)
        return jsonify(json.loads(serialized)), status
    except Exception as e:
        # Fallback for extreme cases
        return jsonify({
            "success": False,
            "error": "Serialization Error",
            "message": str(e)
        }), 500
