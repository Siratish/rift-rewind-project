# Rift Trivia (rift-rewind-project)

A full-stack serverless app that generates League of Legends trivia from your match history. Frontend is a Vite + React single-page app; backend is AWS CDK (Lambdas, Step Functions, Glue, Bedrock KB, WebSocket API, S3).

## Quick start

- Frontend dev server: see Deployment – Frontend
- Backend deploy (CDK): see Deployment – Backend (CDK)

## Deployment – Backend (CDK) ⭐

This project ships with an AWS CDK stack that deploys the entire serverless backend in one go:
- S3 data bucket (versioned, encrypted)
- 6 Lambda functions
- Step Functions state machine
- Glue ETL job (PySpark)
- WebSocket API Gateway
- Bedrock Knowledge Base

### Prerequisites

- AWS account with permissions for: Lambda, S3, Step Functions, Glue, API Gateway, SSM, Bedrock
- Node.js (for CDK CLI) and Python 3.11+ (for CDK app)
- AWS CLI configured

### Configure

Edit `backend/cdk/cdk.context.json` and set the required values:

```json
{
	"bucket_name": "your-unique-bucket-name",
	"riot_api_key_param": "/rift-rewind/riot-api-key",
	"bedrock_model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0"
}
```

Store your Riot API key in SSM Parameter Store (replace the value and region):

```powershell
aws ssm put-parameter --name "/rift-rewind/riot-api-key" --value "YOUR_RIOT_API_KEY" --type "SecureString" --region <your-region>
```

### Deploy

```powershell
# From repository root
cd backend/cdk

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install CDK dependencies
pip install -r requirements.txt

# Install CDK CLI (if not already installed)
npm install -g aws-cdk

# First-time only per account+region
cdk bootstrap

# Review changes, then deploy
cdk diff
cdk deploy
```

### Outputs you’ll need

After deployment, note these outputs printed by CDK:
- `RiftTriviaStack.RiotApiFunctionUrl` – use as `VITE_API_BASE` in the frontend
- `RiftTriviaStack.WebSocketURL` – use as `VITE_WS_URL` in the frontend
- `RiftTriviaStack.S3BucketName`
- `RiftTriviaStack.StateMachineArn`
- `RiftTriviaStack.KnowledgeBaseId` and `RiftTriviaStack.DataSourceId` (for diagnostics/manual syncs)

If this is your very first run, you can optionally trigger a data source sync after the first summary file is produced in `s3://<bucket>/summary/...`:

```powershell
aws bedrock-agent start-ingestion-job --knowledge-base-id <KB_ID> --data-source-id <DS_ID> --region <your-region>
```

More details: `backend/cdk/README.md` and `backend/BEDROCK_KNOWLEDGE_BASE.md`.

## Deployment – Frontend (Vite + React)

Project lives in `frontend/`.

### Environment variables

Create `frontend/.env` (or `.env.local`) with:

```dotenv
# Backend HTTP endpoint (CDK output `RiotApiFunctionUrl`) invoking riot-api-function
VITE_API_BASE=https://<random-hash>.lambda-url.<region>.on.aws

# WebSocket URL from CDK outputs
VITE_WS_URL=wss://<api-id>.execute-api.<region>.amazonaws.com/production
```

### Local development

```powershell
cd frontend
npm install
npm run dev
```

### Production build

```powershell
cd frontend
npm install
npm run build
npm run preview   # optional local preview of the production build
```

### Hosting options

- Any static host (S3 + CloudFront, Vercel, Netlify, GitHub Pages, etc.) – upload `frontend/dist/` contents
- For S3 + CloudFront, ensure SPA rewrite of 404s to `/index.html`

## Repository structure

```
backend/
	cdk/                 # CDK app (Python) – full backend infra
	*.md                 # Deployment and KB docs
frontend/              # Vite + React SPA (Rift Trivia UI)
README.md              # This file
```

## Troubleshooting

- CDK errors about missing context: ensure `bucket_name` and `riot_api_key_param` are set in `backend/cdk/cdk.context.json`
- WebSocket not connecting: confirm `VITE_WS_URL` matches the CDK output and stage is `production`
- 404 / CORS errors calling API: ensure you used the `RiotApiFunctionUrl` CDK output as `VITE_API_BASE` and method is POST
- No facts generated: ensure the Glue job produced a summary under `s3://<bucket>/summary/...` and the ingestion job succeeded