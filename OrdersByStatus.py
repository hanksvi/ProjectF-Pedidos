import os
import json
import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal
from utils import response

ddb = boto3.resource("dynamodb")
orders_table = ddb.Table(os.environ.get("ORDERS_TABLE", "Orders"))

VALID_STATUSES = [
    "created",
    "preparing",
    "ready",
    "delivering",
    "delivered",
    "cancelled"
]


def clean_decimals(obj):
    if isinstance(obj, list):
        return [clean_decimals(i) for i in obj]
    if isinstance(obj, dict):
        return {k: clean_decimals(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    return obj


def lambda_handler(event, context):
    try:
        query_params = event.get("queryStringParameters") or {}
        status = query_params.get("status") if query_params else None

        if not status:
            return response(400, {"message": "status query parameter is required"})

        if status not in VALID_STATUSES:
            return response(400, {
                "message": f"Invalid status. Valid statuses: {', '.join(VALID_STATUSES)}"
            })

        # 🔍 Query usando GSI OrdersByStatus
        resp = orders_table.query(
            IndexName="OrdersByStatus",
            KeyConditionExpression=Key("status").eq(status)
        )

        items = resp.get("Items", [])

        # Opcional: orden por fecha desc
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        items = clean_decimals(items)

        return response(200, {
            "success": True,
            "data": items
        })

    except Exception as e:
        print(f"Error listing orders by status: {str(e)}")
        return response(500, {
            "message": "Error listing orders by status",
            "error": str(e)
        })
