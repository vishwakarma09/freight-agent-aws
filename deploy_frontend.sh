#!/bin/bash
# Exit on error
set -e

# Load root .env file if it exists
if [ -f .env ]; then
  # Use a subshell or env to avoid polluting shell, but since it's a script we can just export
  # Also handle potential carriage returns and spaces
  export $(grep -v '^#' .env | xargs)
fi

STAGE=${1:-dev}

# Determine AWS Region (default to us-east-2 as defined in serverless.yml)
AWS_REGION=${AWS_REGION:-us-east-2}

echo "Retrieving AWS Account ID..."
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET_NAME="freight-agent-frontend-${STAGE}-${AWS_ACCOUNT_ID}"

echo "Target Frontend S3 Bucket: ${BUCKET_NAME}"

# Fetch API URL from .env, or try to get it from serverless info if not set
if [ -z "$API_URL" ]; then
  echo "API_URL not found in .env. Attempting to fetch from Serverless deployment info..."
  API_URL=$(npx serverless info --stage ${STAGE} --region ${AWS_REGION} | grep -oE "https://[a-zA-Z0-9.-]+\.execute-api\.[a-z0-9-]+\.amazonaws\.com" | head -n 1)
fi

if [ -z "$API_URL" ]; then
  echo "Error: Could not determine API_URL. Please set it in your .env file or deploy the backend first."
  exit 1
fi

echo "Backend API URL: ${API_URL}"

# Build the frontend
echo "Installing frontend dependencies..."
cd frontend
npm install --legacy-peer-deps

echo "Building frontend with Vite..."
VITE_API_URL="${API_URL}" npm run build

# Deploy to S3
echo "Uploading assets to S3 bucket ${BUCKET_NAME}..."
aws s3 sync dist/ "s3://${BUCKET_NAME}" --delete

echo "Deployment complete!"
echo "Frontend website is available at: http://${BUCKET_NAME}.s3-website.${AWS_REGION}.amazonaws.com/"
