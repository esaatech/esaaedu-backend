# Google Secret Manager Setup Guide

This guide explains how to set up Google Secret Manager for storing Firebase credentials securely.

## Why Use Google Secret Manager?

- **Security**: Secrets are encrypted and managed by Google Cloud
- **No PEM Issues**: Raw private keys are stored without escaping issues
- **Centralized Management**: All secrets in one place
- **Access Control**: Fine-grained permissions
- **Audit Logging**: Track who accessed what secrets

## Setup Steps

### 1. Enable Secret Manager API

```bash
gcloud services enable secretmanager.googleapis.com
```

### 2. Create Secrets

You have two options for storing Firebase credentials:

#### Option A: Store Complete Firebase Service Account JSON

```bash
# Create a secret with the complete Firebase service account JSON
gcloud secrets create firebase-service-account \
  --data-file=path/to/your/firebase-service-account.json \
  --replication-policy="automatic"
```

#### Option B: Store Individual Firebase Secrets

```bash
# Create individual secrets for each Firebase credential
gcloud secrets create firebase-project-id --data-file=- <<< "your-firebase-project-id"
gcloud secrets create firebase-private-key-id --data-file=- <<< "your-private-key-id"
gcloud secrets create firebase-private-key --data-file=- <<< "-----BEGIN PRIVATE KEY-----
your-private-key-content-here
-----END PRIVATE KEY-----"
gcloud secrets create firebase-client-email --data-file=- <<< "firebase-adminsdk-xxxxx@your-project.iam.gserviceaccount.com"
gcloud secrets create firebase-client-id --data-file=- <<< "your-client-id"
gcloud secrets create firebase-client-x509-cert-url --data-file=- <<< "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-xxxxx%40your-project.iam.gserviceaccount.com"
```

### 3. Grant Access to Cloud Run Service Account

```bash
# Get your Cloud Run service account
CLOUD_RUN_SA=$(gcloud iam service-accounts list --filter="displayName:Compute Engine default service account" --format="value(email)")

# Grant Secret Manager Secret Accessor role
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:$CLOUD_RUN_SA" \
  --role="roles/secretmanager.secretAccessor"
```

### 4. Update GitHub Secrets

Remove these Firebase secrets from GitHub (they're now in Secret Manager):
- `FIREBASE_PRIVATE_KEY_ID`
- `FIREBASE_PRIVATE_KEY`
- `FIREBASE_CLIENT_EMAIL`
- `FIREBASE_CLIENT_ID`
- `FIREBASE_CLIENT_X509_CERT_URL`

Keep only:
- `FIREBASE_PROJECT_ID` (needed to identify which project's secrets to access)

### 5. Test Locally

For local development, you can still use environment variables by setting `USE_SECRET_MANAGER=False` in your `.env` file.

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `FIREBASE_PROJECT_ID` | Your Firebase project ID | Yes |
| `USE_SECRET_MANAGER` | Whether to use Secret Manager (True for production) | Yes |

## Secret Names

The application looks for these secret names in Google Secret Manager:

### Option A (Recommended): Single JSON Secret
- `firebase-service-account` - Complete Firebase service account JSON

### Option B: Individual Secrets
- `firebase-project-id`
- `firebase-private-key-id`
- `firebase-private-key`
- `firebase-client-email`
- `firebase-client-id`
- `firebase-client-x509-cert-url`

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure the Cloud Run service account has `secretmanager.secretAccessor` role
2. **Secret Not Found**: Check secret names match exactly
3. **Invalid JSON**: For Option A, ensure the JSON is valid
4. **PEM Format**: For Option B, ensure private key includes `-----BEGIN PRIVATE KEY-----` and `-----END PRIVATE KEY-----`

### Debug Commands

```bash
# List all secrets
gcloud secrets list

# View a secret
gcloud secrets versions access latest --secret="firebase-service-account"

# Test access from Cloud Run
gcloud run services proxy little-learners-backend --port=8080
curl http://localhost:8080/api/health/
```

## Benefits

- ✅ No more PEM escaping issues
- ✅ Centralized secret management
- ✅ Better security posture
- ✅ Audit trail
- ✅ Automatic rotation support
- ✅ Reduced GitHub secrets complexity
