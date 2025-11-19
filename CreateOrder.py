import os, json, uuid
import boto3
from datetime import datetime, timezone
from utils import response
ddb = boto3.resource('dynamodb')
orders_table = ddb.Table(os.environ.get("ORDERS_TABLE", "Orders"))


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return response(400, {"message": "Invalid JSON body"})

    
    # Validaciones
    required_fields = ["customer_id", "items"]
    for field in required_fields:
        if field not in body:
            return response(400, {"message": f"{field} is required"})

    if not isinstance(body["items"], list) or len(body["items"]) == 0:
        return response(400, {"message": "items must be a non-empty list"})

    # Validar cada item
    for item in body["items"]:
        if "product_id" not in item or "quantity" not in item:
            return response(400, {"message": "Each item must contain product_id and quantity"})

   
    total = 0
    for item in body["items"]:
        unit_price = item.get("price", 0) 
        if not isinstance(unit_price, (int, float)):
            unit_price = 0
        total += unit_price * item["quantity"]


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

    # Guardar en DynamoDB
    try:
        orders_table.put_item(Item=order)
    except Exception as e:
        print(f"Error saving order: {str(e)}")
        return response(500, {"message": "Error creating order"})

    # Response
    return response(201, {
        "success": True,
        "message": "Pedido creado correctamente",
        "data": order
    })