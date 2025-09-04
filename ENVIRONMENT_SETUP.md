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

### Local .env File
Create a `.env` file in your project root:

```env
# Django Configuration
SECRET_KEY=django-insecure-*%%)uc!v428r3q#r_dbt$j&a0u(5@mnv4rju4gryzxsh&ee&k*
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration (Development - SQLite)
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
- Uses SQLite database
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
- Verify Cloud SQL instance is running
- Check IP address whitelist
- Ensure SSL is enabled

### Firebase Authentication Issues
- Verify Firebase project configuration
- Check service account permissions
- Ensure all Firebase secrets are set correctly

### CORS Issues
- Update CORS_ALLOWED_ORIGINS with your frontend URL
- Check ALLOWED_HOSTS includes your Cloud Run URL
