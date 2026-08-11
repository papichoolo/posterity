# Posterity 🕰️

**Seal your life resolutions in a time capsule. Get periodic email check-ins.**

A fully serverless AWS app that costs $0/month. Built with S3, API Gateway, Lambda, DynamoDB, EventBridge, and SES.

---

## Architecture

```
S3 Static Site → API Gateway → Lambda (ingest) → DynamoDB
                                                      ↑
                EventBridge (daily cron) → Lambda (mailer) → SES (email)
```

## Prerequisites

1. **AWS CLI** configured with credentials (`aws configure`)
2. **AWS SAM CLI** installed ([install guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html))
3. **Python 3.12** (for local testing)

## Deployment

### 1. Verify your sender email in SES

```bash
aws ses verify-email-identity --email-address your-email@example.com --region us-east-1
```

Check your inbox and click the verification link.

### 2. Build and deploy

```bash
# Build the SAM application
sam build

# Deploy (first time — interactive)
sam deploy --guided

# Subsequent deploys
sam deploy
```

During guided deploy, you'll be asked for:
- **Stack Name**: `posterity` (or any name)
- **AWS Region**: `us-east-1` (or your preferred region)
- **SenderEmail**: Your verified SES email address
- **Stage**: `prod`

### 3. Note the API URL

After deploy, SAM outputs the API Gateway URL:

```
Outputs:
  ApiUrl: https://abc123.execute-api.us-east-1.amazonaws.com/prod
```

### 4. Update the frontend

Edit `frontend/index.html` and replace `YOUR_API_GATEWAY_URL_HERE` with the actual API URL.

### 5. Upload the frontend to S3

```bash
# Get the bucket name from SAM outputs
BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name posterity \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
  --output text)

# Upload
aws s3 sync frontend/ s3://$BUCKET_NAME/
```

### 6. Access your app

The frontend URL is in SAM outputs:
```
FrontendUrl: http://posterity-frontend-123456789012-prod.s3-website-us-east-1.amazonaws.com
```

## Local Testing

```bash
# Test the ingest function
sam local invoke IngestFunction -e events/test_ingest.json

# Test the mailer function (requires DynamoDB access)
sam local invoke MailerFunction -e events/test_mailer.json
```

## API Reference

### POST /capsules

Create a new time capsule.

**Request:**
```json
{
  "name": "Sourav",
  "email": "sourav@example.com",
  "resolutions": [
    "Read 50 books",
    "Run a marathon",
    "Learn guitar"
  ],
  "checkInDays": 180,
  "planDurationDays": 730
}
```

**Response (201):**
```json
{
  "message": "Time capsule created!",
  "capsuleId": "550e8400-e29b-41d4-a716-446655440000",
  "nextCheckIn": "2027-02-05",
  "endsAt": "2028-08-09",
  "totalCheckIns": 4
}
```

## Cost

| Service | Monthly Cost |
|---|---|
| S3 | $0.00 |
| API Gateway | $0.00 |
| Lambda | $0.00 |
| DynamoDB | $0.00 |
| EventBridge | $0.00 |
| SES | $0.00 |
| **Total** | **$0.00** |

All services used have permanent always-free tiers that far exceed this app's usage.

## Teardown

```bash
# Empty the S3 bucket first (required before stack deletion)
aws s3 rm s3://$BUCKET_NAME --recursive

# Delete the entire stack
sam delete --stack-name posterity
```

## License

MIT
