import json, boto3, os

sfn = boto3.client('stepfunctions')

STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']
API_GATEWAY_ENDPOINT = os.environ['API_GATEWAY_ENDPOINT']

api = boto3.client('apigatewaymanagementapi', endpoint_url=API_GATEWAY_ENDPOINT)

def lambda_handler(event, context):
    print(event)
    connection_id = event['requestContext']['connectionId']
    body = json.loads(event['body'])

    if (not body.get("summary_exists")) or (not body.get("final_exists")):
        running_executions = []
        next_token = None
        
        while True:
            params = {
                'stateMachineArn': STATE_MACHINE_ARN,
                'statusFilter': 'RUNNING'
            }
            if next_token:
                params['nextToken'] = next_token
            
            response = sfn.list_executions(**params)
            running_executions.extend(response['executions'])
            
            next_token = response.get('nextToken')
            if not next_token:
                break
        
        for execution in running_executions:
            exec_desc = sfn.describe_execution(executionArn=execution['executionArn'])
            existing_input = json.loads(exec_desc['input'])
            
            if existing_input.get("puuid") == body.get("puuid") and existing_input.get("year") == body.get("year"):
                if connection_id:
                    api.post_to_connection(
                        ConnectionId=connection_id,
                        Data=json.dumps({"state":"BUSY"})
                    )
                return {"statusCode": 200, "body": "Execution already running"}
    
    sfn.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        input=json.dumps({
            "puuid": body.get("puuid"),
            "year": body.get("year"),
            "summary_exists": body.get("summary_exists"),
            "final_exists": body.get("final_exists"),
            "routing_value": body.get("routing_value"),
            "connectionId": connection_id
        })
    )

    return {"statusCode": 200, "body": "Execution started"}
