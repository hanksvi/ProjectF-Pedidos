import os, json
import boto3
from datetime import datetime, timezone
from utils import response

ddb = boto3.resource('dynamodb')
orders_table = ddb.Table(os.environ.get("ORDERS_TABLE", "Orders"))

FINAL_STATUSES = ["delivered", "cancelled"]


def lambda_handler(event, context):
    path_params = event.get("pathParameters") or {}
    order_id = path_params.get("order_id")

    if not order_id:
        return response(400, {"message": "order_id is required in path"})

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return response(400, {"message": "Invalid JSON body"})

    cancelled_by = body.get("cancelled_by", "system")
    reason = body.get("reason", "")

    try:
        # Obtener pedido
        result = orders_table.get_item(Key={"order_id": order_id})
        if "Item" not in result:
            return response(404, {"message": "Order not found"})

        order = result["Item"]
        current_status = order.get("status", "created")

        if current_status in FINAL_STATUSES:
            return response(400, {
                "message": f"Cannot cancel an order with status {current_status}"
            })

        now = datetime.now(timezone.utc).isoformat()
        history_entry = {
            "action": "cancelled",
            "at": now,
            "by": cancelled_by,
            "reason": reason
        }

        update_result = orders_table.update_item(
            Key={"order_id": order_id},
            UpdateExpression=(
                "SET #status = :cancelled, "
                "updated_at = :updated_at, "
                "history = list_append(if_not_exists(history, :empty_list), :history_entry)"
            ),
            ExpressionAttributeNames={
                "#status": "status"
            },
            ExpressionAttributeValues={
                ":cancelled": "cancelled",
                ":updated_at": now,
                ":history_entry": [history_entry],
                ":empty_list": []
            },
            ReturnValues="ALL_NEW"
        )

        updated_order = update_result.get("Attributes", {})

        return response(200, {
            "success": True,
            "message": "Order cancelled successfully",
            "data": updated_order
        })

    except Exception as e:
        print(f"Error cancelling order: {str(e)}")
        return response(500, {"message": "Error cancelling order"})
