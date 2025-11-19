import json
import boto3
from datetime import datetime, timezone
from decimal import Decimal
def response(status, body):
    body = clean_decimals(body)
    return {
        "statusCode": status,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "OPTIONS,POST,GET,PUT,DELETE"
        },
        "body": json.dumps(body)
    }


from decimal import Decimal

def clean_decimals(obj):
    if isinstance(obj, list):
        return [clean_decimals(i) for i in obj]
    if isinstance(obj, dict):
        return {k: clean_decimals(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        # si es número entero, devuelve int; si no, float
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


events_client = boto3.client("events")

def publish_order_event(detail_type: str, detail: dict, source: str = "orders.service"):
    
    #Envía un evento a EventBridge
    detail = dict(detail)  # copiar por seguridad
    detail["event_time"] = datetime.now(timezone.utc).isoformat()

    # limpiar Decimals para que json.dumps no falle
    detail = clean_decimals(detail)

    events_client.put_events(
        Entries=[
            {
                "Source": source,
                "DetailType": detail_type,
                "Detail": json.dumps(detail),
                "EventBusName": "default",  
            }
        ]
    )
