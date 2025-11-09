import json
import boto3
import os

API_GATEWAY_ENDPOINT = os.environ['API_GATEWAY_ENDPOINT']

api = boto3.client('apigatewaymanagementapi', endpoint_url=API_GATEWAY_ENDPOINT)

def lambda_handler(event, context):
    connection_id = event['connectionId']
    if connection_id:
        api.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps({"state":"FAIL"})
        )
    return {
        'statusCode': 200,
        'body': json.dumps('FAIL')
    }
