# Environment Setup Guide

## 🚀 Production Environment (Cloud Run + Cloud SQL)

### Required GitHub Secrets

Add these secrets to your GitHub repository:
**Settings** → **Secrets and variables** → **Actions** → **New repository secret**

#### Database Configuration
```
DB_ENGINE = postgresql
DB_NAME = little_learners_tech
DB_USER = postgres
DB_PASSWORD = [your-sql-password]
DB_HOST = 104.197.207.176
DB_PORT = 5432
```

#### Django Configuration
```
SECRET_KEY = [your-production-secret-key]
DEBUG = False
ALLOWED_HOSTS = [your-cloud-run-url].run.app
```

#### Firebase Configuration
```
FIREBASE_PROJECT_ID = [your-firebase-project-id]
FIREBASE_PRIVATE_KEY_ID = [your-firebase-private-key-id]
FIREBASE_PRIVATE_KEY = [your-firebase-private-key]
FIREBASE_CLIENT_EMAIL = [your-firebase-client-email]
FIREBASE_CLIENT_ID = [your-firebase-client-id]
FIREBASE_CLIENT_X509_CERT_URL = [your-firebase-cert-url]
```

#### CORS Configuration
```
CORS_ALLOWED_ORIGINS = https://your-frontend-domain.com
```

#### Google Cloud Configuration
```
GCP_PROJECT_ID = [your-gcp-project-id]
GCP_SA_KEY = [your-service-account-json-key]
```

## 🛠️ Development Environment (Local)

### Cloud SQL Auth Proxy (recommended for PostgreSQL)

Use this instead of allowlisting a public IP. ExpressVPN (and similar) rotate egress IPs, so authorized networks break often. Auth Proxy uses Google credentials and does not need an authorized-network entry.

1. Install once:
   ```bash
   brew install cloud-sql-proxy
   gcloud auth application-default login
   ```
2. Start the proxy (keep this terminal open):
   ```bash
   ./scripts/start-cloud-sql-proxy.sh
   ```
   Default instance: `esaasolution:us-central1:sbtacedemy` on `127.0.0.1:5433`.
3. Point local `.env` at the proxy:
   ```env
   DB_ENGINE=postgresql
   DB_NAME=stbacedemy-backened
   DB_USER=postgres
   DB_PASSWORD=your-sql-password
   DB_HOST=127.0.0.1
   DB_PORT=5433
   DB_SSLMODE=disable
   GCP_PROJECT_ID=esaasolution
   ```
4. Run Django as usual (`python manage.py runserver`, shell, etc.).

Your Google account (or `GOOGLE_APPLICATION_CREDENTIALS` service account) needs the **Cloud SQL Client** role on project `esaasolution`.

### Local .env File
Create a `.env` file in your project root:

```env
# Django Configuration
SECRET_KEY=django-insecure-*%%)uc!v428r3q#r_dbt$j&a0u(5@mnv4rju4gryzxsh&ee&k*
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration — SQLite for offline work, or PostgreSQL via Auth Proxy above
DB_ENGINE=sqlite

# CORS Configuration (Development)
CORS_ALLOW_ALL_ORIGINS=True

# Firebase Configuration (Development)
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_PRIVATE_KEY_ID=your-firebase-private-key-id
FIREBASE_PRIVATE_KEY=your-firebase-private-key
FIREBASE_CLIENT_EMAIL=your-firebase-client-email
FIREBASE_CLIENT_ID=your-firebase-client-id
FIREBASE_CLIENT_X509_CERT_URL=your-firebase-cert-url
```

## 🔄 Environment Switching

### Development (Default)
- Uses SQLite, or PostgreSQL through Cloud SQL Auth Proxy
- Debug mode enabled
- CORS allows all origins
- Uses local .env file

### Production (GitHub Actions)
- Uses Cloud SQL PostgreSQL
- Debug mode disabled
- CORS restricted to specific origins
- Uses GitHub Secrets

## 📋 Next Steps

1. **Set up GitHub Secrets** with the values above
2. **Create a Google Cloud Service Account** and download the JSON key
3. **Push your code to GitHub** to trigger the deployment
4. **Test your Cloud Run service** once deployed

## 🔧 Troubleshooting

### Database Connection Issues
- Prefer Cloud SQL Auth Proxy for local work (`./scripts/start-cloud-sql-proxy.sh`)
- Verify Cloud SQL instance is running
- Public IP access needs an authorized network IP (brittle with VPNs)
- For Auth Proxy / unix sockets, use `DB_SSLMODE=disable`

### Firebase Authentication Issues
- Verify Firebase project configuration
- Check service account permissions
- Ensure all Firebase secrets are set correctly

### CORS Issues
- Update CORS_ALLOWED_ORIGINS with your frontend URL
- Check ALLOWED_HOSTS includes your Cloud Run URL
