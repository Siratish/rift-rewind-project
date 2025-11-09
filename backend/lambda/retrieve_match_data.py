import json
import time
import boto3
import urllib3
import os
from urllib.parse import quote
from datetime import datetime, timezone

BUCKET = os.environ['S3_BUCKET']
SSM_PARAMETER_NAME = os.environ['RIOT_API_KEY_SSM_PARAM']
API_GATEWAY_ENDPOINT = os.environ['API_GATEWAY_ENDPOINT']

s3 = boto3.client("s3")

ssm = boto3.client('ssm')
parameter = ssm.get_parameter(
    Name=SSM_PARAMETER_NAME,
    WithDecryption=True
)
api_key = parameter['Parameter']['Value']

http = urllib3.PoolManager()
headers = {'X-Riot-Token': api_key}
api = boto3.client('apigatewaymanagementapi', endpoint_url=API_GATEWAY_ENDPOINT)

def fetch_match_ids(puuid, routing_value, start_time=None, end_time=None, start=0, count=100):
    url = f"https://{routing_value}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {"start": start, "count": count}
    if start_time:
        params["startTime"] = start_time
    if end_time:
        params["endTime"] = end_time
    resp = http.request('GET', url, headers=headers, fields=params)
    if resp.status == 429:
        time.sleep(2)
        return fetch_match_ids(puuid, routing_value, start_time, end_time, start, count)
    elif resp.status != 200:
        raise Exception(f"Failed to fetch match IDs: {resp.status}, {resp.data.decode('utf-8')}")
    return json.loads(resp.data.decode('utf-8'))

def fetch_match_data(match_id, routing_value):
    url = f"https://{routing_value}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    resp = http.request('GET', url, headers=headers)
    if resp.status == 429:
        time.sleep(1)
        return fetch_match_data(match_id, routing_value)
    elif resp.status != 200:
        return None
    return json.loads(resp.data.decode('utf-8'))

def list_existing_match_ids(puuid):
    prefix = f"match-history/{puuid}/stats/"
    existing_ids = set()
    continuation_token = None
    while True:
        kwargs = {"Bucket": BUCKET, "Prefix": prefix}
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token
        result = s3.list_objects_v2(**kwargs)
        if "Contents" in result:
            for obj in result["Contents"]:
                key = obj["Key"]
                match_id = key.split("/")[-1].replace(".json", "")
                existing_ids.add(match_id)
        if result.get("IsTruncated"):
            continuation_token = result.get("NextContinuationToken")
        else:
            break
    return existing_ids

def lambda_handler(event, context):
    puuid = event['puuid']
    year = event['year']
    routing_value = event['routing_value']
    connection_id = event['connectionId']

    start_of_year = int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp())
    end_of_year = int(datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp())

    existing_match_ids = list_existing_match_ids(puuid)

    all_match_ids = []
    start = 0
    batch_size = 100
    while True:
        batch = fetch_match_ids(
            puuid,
            routing_value,
            start_time=start_of_year,
            end_time=end_of_year,
            start=start,
            count=batch_size
        )
        if not batch:
            break
        all_match_ids.extend(batch)
        start += batch_size
    new_match_ids = [m for m in all_match_ids if m not in existing_match_ids]

    if connection_id:
        api.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps({"state":"START_RETRIEVE_MATCH","total":len(all_match_ids)})
        )

    for match_id in new_match_ids:
        match_data = fetch_match_data(match_id, routing_value)
        if match_data:
            player_stats = extract_player_stats(match_data, puuid)
            if player_stats:
                match_id = match_data["metadata"]["matchId"]
                timestamp = match_data["info"]["gameStartTimestamp"] // 1000
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                stats_key = f"match-history/{puuid}/stats/{dt.year}/{dt.month:02d}/{dt.day:02d}/{match_id}.json"
                s3.put_object(
                    Bucket=BUCKET,
                    Key=stats_key,
                    Body=json.dumps(player_stats),
                    ContentType='application/json'
                ) 
                existing_match_ids.add(match_id)
                if connection_id:
                    api.post_to_connection(
                        ConnectionId=connection_id,
                        Data=json.dumps({"state":"RETRIEVING_MATCH","count":len(existing_match_ids)})
                    )

    if connection_id:
        api.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps({"state":"PROCESSING_MATCH"})
        )
    
    return {
        'complete': len(existing_match_ids) == len(all_match_ids)
    }
        

def extract_player_stats(match_data, puuid):
    try:
        participants = match_data['info']['participants']
        player_data = next((p for p in participants if p['puuid'] == puuid), None)
        if not player_data:
            return None
        stats = {
            'matchId': match_data['metadata']['matchId'],
            'gameCreation': match_data['info']['gameCreation'],
            'gameDuration': match_data['info']['gameDuration'],
            'gameMode': match_data['info']['gameMode'],
            'queueId': match_data['info']['queueId'],
            'championName': player_data['championName'],
            'championId': player_data['championId'],
            'teamPosition': player_data['teamPosition'],
            'individualPosition': player_data['individualPosition'],
            'kills': player_data['kills'],
            'deaths': player_data['deaths'],
            'assists': player_data['assists'],
            'totalMinionsKilled': player_data['totalMinionsKilled'],
            'neutralMinionsKilled': player_data['neutralMinionsKilled'],
            'goldEarned': player_data['goldEarned'],
            'totalDamageDealtToChampions': player_data['totalDamageDealtToChampions'],
            'totalDamageTaken': player_data['totalDamageTaken'],
            'visionScore': player_data['visionScore'],
            'win': player_data['win'],
            'items': [
                player_data['item0'],
                player_data['item1'],
                player_data['item2'],
                player_data['item3'],
                player_data['item4'],
                player_data['item5'],
                player_data['item6']
            ],
            'summoner1Id': player_data['summoner1Id'],
            'summoner2Id': player_data['summoner2Id'],
            'perks': {
                'primaryStyle': player_data['perks']['styles'][0]['style'],
                'subStyle': player_data['perks']['styles'][1]['style'],
                'primaryPerk': player_data['perks']['styles'][0]['selections'][0]['perk']
            }
        }
        return stats
    except Exception as e:
        print(f"Error extracting player stats: {str(e)}")
        return None
