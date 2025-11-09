import json
import time
import boto3
import urllib3
import os
from urllib.parse import quote
from datetime import datetime, timezone

BUCKET = os.environ['S3_BUCKET']
SSM_PARAMETER_NAME = os.environ['RIOT_API_KEY_SSM_PARAM']

s3 = boto3.client("s3")

# Get API key from Parameter Store
ssm = boto3.client('ssm')
parameter = ssm.get_parameter(
    Name=SSM_PARAMETER_NAME,
    WithDecryption=True
)
api_key = parameter['Parameter']['Value']

# Initialize HTTP client
http = urllib3.PoolManager()
headers = {'X-Riot-Token': api_key}

def file_exists(key):
    try:
        s3.head_object(Bucket=BUCKET, Key=key)
        return True
    except s3.exceptions.ClientError:
        return False


def lambda_handler(event, context):
    """
    Resolve Riot ID to PUUID and basic summoner info; check S3 for existing summary/final.
    Accepts body with either { riotId, region } or legacy { summonerName, region }.
    """
    try:
        # Parse the request
        body = json.loads(event['body']) if isinstance(event.get('body'), (str, bytes)) else (event.get('body') or {})
        riot_id = (body.get('riotId') or body.get('summonerName') or '').strip()
        region = (body.get('region') or 'na1').strip().lower()
        
        # Validate input
        if not riot_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Riot ID is required (e.g., GameName#TAG)'})
            }
        if '#' not in riot_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Please use Riot ID format: GameName#TAG (e.g., Hide on bush#KR1)'})
            }
        
        # Step 1: Get account PUUID using Riot ID
        game_name, tag_line = riot_id.split('#', 1)
        game_name = quote(game_name)
        tag_line = quote(tag_line)
        
        routing_value = get_routing_value(region)
        # SEA routing uses Asia for the account lookup
        account_routing = 'asia' if routing_value == 'sea' else routing_value
        account_url = f"https://{account_routing}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
        
        account_response = http.request('GET', account_url, headers=headers)
        
        if account_response.status == 404:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Riot ID not found. Check spelling and region.'})
            }
        elif account_response.status != 200:
            return {
                'statusCode': account_response.status,
                'body': json.dumps({'error': f'Failed to fetch account: {account_response.status}'})
            }
        
        account_data = json.loads(account_response.data.decode('utf-8'))
        puuid = account_data['puuid']
        resolved_riot_id = f"{account_data['gameName']}#{account_data['tagLine']}"
        
        # Step 2: Get summoner data by PUUID (platform region)
        summoner_url = f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
        summoner_response = http.request('GET', summoner_url, headers=headers)
        if summoner_response.status != 200:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to fetch summoner data'})
            }
        summoner_data = json.loads(summoner_response.data.decode('utf-8'))
        
        # Last year
        current_year = datetime.now(timezone.utc).year
        last_year = current_year - 1

        summary_key = f"summary/{puuid}/final_summary_{last_year}.json"
        final_key = f"player_facts/{puuid}/{last_year}.json"
        summary_exists = file_exists(summary_key)
        final_exists = file_exists(final_key)

        response_data = {
            'summoner': {
                'name': resolved_riot_id,
                'gameName': account_data['gameName'],
                'tagLine': account_data['tagLine'],
                'profileIconId': summoner_data['profileIconId'],
                'region': region,
                'level': summoner_data['summonerLevel'],
                'puuid': puuid
            },
            'routing_value': routing_value,
            'year': last_year,
            'summary_exists': summary_exists,
            'final_exists': final_exists
        }
        
        return {
            'statusCode': 200,
            'body': json.dumps(response_data)
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }

def get_routing_value(region):
    routing_map = {
        'na1': 'americas',
        'br1': 'americas',
        'la1': 'americas',
        'la2': 'americas',
        'euw1': 'europe',
        'eun1': 'europe',
        'tr1': 'europe',
        'ru': 'europe',
        'kr': 'asia',
        'jp1': 'asia',
        'oc1': 'sea',
        'sg2': 'sea',
        'tw2': 'sea',
        'vn2': 'sea'
    }
    return routing_map.get(region, 'americas')
