import os, json
import boto3
from datetime import datetime, timezone
from utils import response
from utils import publish_order_event

ddb = boto3.resource('dynamodb')
orders_table = ddb.Table(os.environ.get("ORDERS_TABLE", "Orders"))

VALID_STATUSES = ["created", "preparing", "ready", "delivering", "delivered"]
VALID_TRANSITIONS = {
    "created":    ["preparing"],
    "preparing":  ["ready"],
    "ready":      ["delivering"],
    "delivering": ["delivered"],
    "delivered":  []  # ya finalizado
}


def lambda_handler(event, context):
    path_params = event.get("pathParameters") or {}
    order_id = path_params.get("order_id")

    if not order_id:
        return response(400, {"message": "order_id is required in path"})

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return response(400, {"message": "Invalid JSON body"})

    new_status = body.get("status")
    updated_by = body.get("updated_by", "system")

    if new_status not in VALID_STATUSES:
        return response(400, {
            "message": f"Invalid status. Valid statuses: {', '.join(VALID_STATUSES)}"
        })

    # No se permite cambiar a "cancelled" aquí, eso lo maneja otro lambda
    if new_status == "cancelled":
        return response(400, {"message": "Use cancel order endpoint to cancel orders"})

    # Obtener pedido actual
    try:
        result = orders_table.get_item(Key={"order_id": order_id})
        if "Item" not in result:
            return response(404, {"message": "Order not found"})

        order = result["Item"]
        current_status = order.get("status", "created")

        allowed_next = VALID_TRANSITIONS.get(current_status, [])
        if new_status not in allowed_next:
            return response(400, {
                "message": f"Invalid transition from {current_status} to {new_status}. "
                           f"Allowed: {', '.join(allowed_next) if allowed_next else 'none'}"
            })

        now = datetime.now(timezone.utc).isoformat()
        history_entry = {
            "action": f"status_changed_{current_status}_to_{new_status}",
            "at": now,
            "by": updated_by
        }

        # Update con retorno del item actualizado
        update_result = orders_table.update_item(
            Key={"order_id": order_id},
            UpdateExpression=(
                "SET #status = :new_status, "
                "updated_at = :updated_at, "
                "history = list_append(if_not_exists(history, :empty_list), :history_entry)"
            ),
            ExpressionAttributeNames={
                "#status": "status"
            },
            ExpressionAttributeValues={
                ":new_status": new_status,
                ":updated_at": now,
                ":history_entry": [history_entry],
                ":empty_list": []
            },
            ReturnValues="ALL_NEW"
        )

        updated_order = update_result.get("Attributes", {})

        try:
            publish_order_event(
                detail_type="OrderStatusUpdated",
                detail={
                    "order_id": order_id,
                    "customer_id": updated_order.get("customer_id"),
                    "old_status": current_status,
                    "new_status": new_status
                }
            )
        except Exception as e:
            print(f"Error publishing OrderStatusUpdated event: {str(e)}")

        return response(200, {
            "success": True,
            "message": "Order status updated successfully",
            "data": updated_order
        })

    except Exception as e:
        print(f"Error updating order status: {str(e)}")
        return response(500, {"message": "Error updating order status"})
