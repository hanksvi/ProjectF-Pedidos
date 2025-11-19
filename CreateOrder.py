import os, json, uuid
import boto3
from datetime import datetime, timezone
from decimal import Decimal
from utils import response

ddb = boto3.resource('dynamodb')
orders_table = ddb.Table(os.environ.get("ORDERS_TABLE", "Orders"))


def lambda_handler(event, context):
    # Parsear body convirtiendo floats a Decimal
    try:
        body = json.loads(event.get("body", "{}"), parse_float=Decimal)
    except json.JSONDecodeError:
        return response(400, {"message": "Invalid JSON body"})

    # Validaciones
    required_fields = ["customer_id", "items"]
    for field in required_fields:
        if field not in body:
            return response(400, {"message": f"{field} is required"})

    if not isinstance(body["items"], list) or len(body["items"]) == 0:
        return response(400, {"message": "items must be a non-empty list"})

    for item in body["items"]:
        if "product_id" not in item or "quantity" not in item:
            return response(400, {"message": "Each item must contain product_id and quantity"})

    # Calcular total usando Decimal
    total = Decimal("0")

    for item in body["items"]:
        unit_price = item.get("price", Decimal("0"))
        quantity = Decimal(item["quantity"])
        total += unit_price * quantity

    # Crear pedido
    order_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()

    order = {
        "order_id": order_id,
        "customer_id": body["customer_id"],
        "status": "created",
        "total": total,
        "items": body["items"],
        "created_at": now,
        "updated_at": now,
        "history": [
            {
                "action": "created",
                "at": now,
                "by": body.get("customer_id", "unknown")
            }
        ]
    }

    # Guardar en DB
    try:
        orders_table.put_item(Item=order)
    except Exception as e:
        print(f"Error saving order: {str(e)}")
        return response(500, {"message": "Error creating order"})

    return response(201, {
        "success": True,
        "message": "Pedido creado correctamente",
        "data": order
    })
