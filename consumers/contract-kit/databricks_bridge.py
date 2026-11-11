"""JSON stdin bridge for non-Python consumers; credentials stay in the environment."""
from datetime import date, datetime
from decimal import Decimal
import json
import sys

from databricks_client import execute


def json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(type(value).__name__)


if __name__ == "__main__":
    request = json.load(sys.stdin)
    result = execute(request["sql"], request.get("parameters", []), consumer=sys.argv[1])
    print(json.dumps(result, default=json_value))
