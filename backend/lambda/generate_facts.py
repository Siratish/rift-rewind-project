import json
import re
import boto3
import os

BUCKET = os.environ['S3_BUCKET']
KB_ID = os.environ['BEDROCK_KB_ID']
REGION = os.environ['AWS_REGION']
MODEL_ID = os.environ['BEDROCK_MODEL_ID']
API_GATEWAY_ENDPOINT = os.environ['API_GATEWAY_ENDPOINT']

bedrock_client = boto3.client('bedrock-agent-runtime', region_name=REGION)
s3 = boto3.client('s3')
api = boto3.client('apigatewaymanagementapi', endpoint_url=API_GATEWAY_ENDPOINT)

def rag_generate(puuid: str, year: int, max_results: int = 15):
    query = """
You are an AI analyst and creative storyteller for League of Legends, combining the roles of:
- A data analyst who understands player performance metrics (kills, assists, win rate, etc.).
- A quiz master who creates fun and clever trivia about gameplay stats.
- A storyteller who writes in a friendly, gamer-savvy tone — suitable for a year-in-review recap.
Your task:
1. Retrieve the player’s summary data from the knowledge base.
2. Generate 10 unique, data-backed facts about their performance over the past year.
    - Each fact must be specific, numerically grounded, and clearly related to the player’s behavior or style.
3. For each fact:
    - Write a fact: a concise, natural-language insight based on their data.
    - Write a context: 1–2 friendly sentences that add personality and commentary — like a fun “color” statement for their playstyle.
    - Write a question: a fun trivia question players can guess about themselves based on that fact.
    - Include choices (for multiple choice) or use True/False format.
    - Provide the correct_answer.
Tone and Style:
- Conversational, positive, and engaging — like a Riot “Year in Review” or a Twitch recap.
- Avoid generic statements. Use numbers and context from the player’s stats.
- Facts should vary (e.g. best champion, favorite role, highest vision score, longest win streak, time trends, etc.).
Output format:
Return a JSON array with the following fields:
[
  {
    "fact": "<data-backed insight>",
    "context": "<short commentary>",
    "question": "<trivia question>",
    "choices": ["A", "B", "C", "D"],
    "correct_answer": "<correct answer>"
  }
]
Output must be **a pure JSON array only**, without any extra text, markdown, or commentary.
    """
    response = bedrock_client.retrieve_and_generate(
        input={'text': query},
        retrieveAndGenerateConfiguration={
            'type': 'KNOWLEDGE_BASE',
            'knowledgeBaseConfiguration': {
                'knowledgeBaseId': KB_ID,
                'modelArn': MODEL_ID,
                'retrievalConfiguration': {
                    'vectorSearchConfiguration': {
                        'numberOfResults': max_results,
                        'filter': {'andAll': [{'equals': {'key': 'puuid','value': puuid}},
                            {'equals': {'key': 'year','value': year}}]}
                    }
                }
            }
        }
    )
    answer = response.get('output', {}).get('text', '')
    return answer

def extract_json_array(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            json_str = match.group(0)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                raise ValueError("Found a JSON-like array but couldn't parse it.")
        else:
            raise ValueError("No JSON array found in text.")

def lambda_handler(event, context):
    puuid = event['puuid']
    year = event['year']
    final_exists = event['final_exists']
    connection_id = event['connectionId']

    if final_exists:
        final_output = json.loads(s3.get_object(Bucket=BUCKET, Key=f'player_facts/{puuid}/{year}.json')['Body'].read().decode('utf-8'))
    else: 
        if connection_id:
            api.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps({"state":"GENERATING_FACTS"})
            )
        final_output = extract_json_array(rag_generate(puuid, year))
        s3.put_object(Body=json.dumps(final_output), Bucket=BUCKET, Key=f'player_facts/{puuid}/{year}.json')
    if connection_id:
        api.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps({"state":"COMPLETE","result":final_output})
        )
    return final_output
