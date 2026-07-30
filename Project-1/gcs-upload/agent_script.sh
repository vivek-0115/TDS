#!/usr/bin/env bash
set -euo pipefail

exec 3>&1  # save stdout
exec > >(tee /tmp/agent_log.jsonl) 2>&1

log_jsonl() {
  local ts
  ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  echo "{\"timestamp\":\"$ts\",\"action\":\"$1\",\"detail\":$2}"
}

log_jsonl "start" "{\"message\":\"Starting Q2: GCS bucket creation and file upload\"}"
log_jsonl "read_config" "{\"file\":\"gcp-cloud-q2-details.json\"}"

BUCKET_NAME="q2-aa41e3a23a16537"
LOCATION="asia-south1"
FILE="eval.jsonl"

log_jsonl "bucket_name" "{\"bucket\":\"$BUCKET_NAME\",\"location\":\"$LOCATION\"}"

# Compute SHA-256 before upload
SHA256=$(shasum -a 256 "$FILE" | cut -d' ' -f1)
log_jsonl "sha256_compute" "{\"file\":\"$FILE\",\"sha256\":\"$SHA256\"}"

# Create bucket
log_jsonl "create_bucket" "{\"action\":\"creating_bucket\",\"bucket\":\"$BUCKET_NAME\",\"location\":\"$LOCATION\"}"
gcloud storage buckets create "gs://$BUCKET_NAME" \
  --location="$LOCATION" \
  --uniform-bucket-level-access
log_jsonl "bucket_created" "{\"bucket\":\"$BUCKET_NAME\",\"status\":\"created\"}"

# Upload file
log_jsonl "upload_file" "{\"action\":\"uploading\",\"file\":\"$FILE\",\"destination\":\"gs://$BUCKET_NAME/$FILE\"}"
gcloud storage cp "$FILE" "gs://$BUCKET_NAME/$FILE"
log_jsonl "file_uploaded" "{\"file\":\"$FILE\",\"destination\":\"gs://$BUCKET_NAME/$FILE\",\"status\":\"uploaded\"}"

# Make bucket publicly readable
log_jsonl "set_public" "{\"action\":\"setting_public_access\",\"bucket\":\"$BUCKET_NAME\"}"
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET_NAME" \
  --member=allUsers \
  --role=roles/storage.objectViewer
log_jsonl "public_access_set" "{\"bucket\":\"$BUCKET_NAME\",\"role\":\"roles/storage.objectViewer\",\"members\":\"allUsers\"}"

# Verify upload and SHA-256
log_jsonl "verify" "{\"action\":\"verifying_upload\"}"
gcloud storage ls "gs://$BUCKET_NAME/"
UPLOADED_SHA=$(gcloud storage cat "gs://$BUCKET_NAME/$FILE" | shasum -a 256 | cut -d' ' -f1)
log_jsonl "sha256_verify" "{\"original_sha256\":\"$SHA256\",\"uploaded_sha256\":\"$UPLOADED_SHA\",\"match\":$([ "$SHA256" = "$UPLOADED_SHA" ] && echo "true" || echo "false")}"

# List bucket details
log_jsonl "bucket_details" "{\"bucket\":\"$BUCKET_NAME\",\"location\":\"$LOCATION\",\"public_url\":\"https://storage.googleapis.com/$BUCKET_NAME/$FILE\"}"

log_jsonl "complete" "{\"message\":\"Q2 completed successfully\",\"bucket\":\"$BUCKET_NAME\",\"file\":\"$FILE\",\"sha256\":\"$SHA256\"}"
