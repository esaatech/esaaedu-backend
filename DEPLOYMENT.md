# Deployment Guide

## 🚀 GitHub Actions & Firebase Setup

### 1. GitHub Secrets Configuration

Add the following secrets to your GitHub repository (`Settings > Secrets and variables > Actions`):

#### Firebase Credentials
```
FIREBASE_PROJECT_ID=kidtech-1b497
FIREBASE_PRIVATE_KEY_ID=f8c1ece280f4c56eb8257097775373c26d986ef3
FIREBASE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCkVMiPj45ghS0T
S2ZV1Hl+ps6LpafADekoMqpGORQ5OIYRIOdafKVFLZ2mDp0Aoa7JYERtxAooWjre
EBqF9tDckQC9685LkcPWy2Kw+3PaHAsWjwS4EBXoT4wW1j8VWrc/vS9zq2wUl06u
KRH51n5zuCoOGt34zghsIUzwnX7/kTukDP/OgWVLho2g3dZyL5SQ8vdPSj8mYVIh
ln7VBpOMbIAylr2jWK5V8IN1QxxKgRFR5BZSo1S/fK1ZLjXZd+t7d7A9X/uyLA71
1pQxipQExNHA9mm+0l/jL15zundUV554Z3SXTl0J/iyTpUb8ij3GqzSMf9joirDk
f70+oierAgMBAAECggEABHXdPgziVHISF7bV7WZ53uR5VZkGoJ0JMM6z0Z5sJYhR
hGjugzyJK0yrYjTGw+UNTFaRKX4ib0319V/wPO80ZBqJL8MVDvbnnw6gfEngHNri
lHK+ezCCTEo8dOkWGdSRqnry9jTJhRWPcSmYyr2IRtqs10QG2mFvjs2EBR0Tjxsa
3fFTvy13X3hDJuIkMW5wJ3Nll4/cGVAGL0pb6sz6mPC6LhAHYV+LyXVSvxt7p0m0
BpdE/V3XJxeGbB5inlbkCbZpjnV+iglCfa9ig1TU4nBZtEQJG56SwxNvHBuOCQ+j
pkfpyedBRqW9R4MRiiYTgV52ez5O0RfPo+Bspod54QKBgQDk7jcVXmnqBI0sYcTQ
uRJ6zas76L5xKiQgNYyG4g1JLDVsMQx1FjTK6R3zHO8PVf8aOlYJAqHGlQaqVwVA
cNDSXvfy4R8FPars3GwroEhfY4Nk3MDtB6lhOOWEEKoRJ/Yk+L2Xjye/Ct+CKSU9
187zK8fgkWEweoNUSvzPUfmJFwKBgQC3wyE/UJXW//mUBtOqgLuBWtK5k6YrPIeb
xqApswelIniVCyw+pU67ETdwC/B6GCrP0r4jV6hrVAQPzmZS44rgxnToU5dUw88E
UTsDG9aHIpllpfPpexd2/EpcYq466TMn5CLnixWhV1YFWmoCeL/nwVZ6zCG7rU0T
Cybp9pdKjQKBgQDcAk9vut+g5iTiXUdvrB0lZdjFZ4T2bqBvT+cwjbhk9RaWVoD5
WZD83JJK3SimHWhfxWZ/nEbq+LeCJsVGS+Vz947knRNZzw0gOym9t3k2KwXQfhLu
+OkAJVT12aoHeNcmauKR8CMrh4CLr4055NfffNjHag/0Lhleff5+I/LjmwKBgGYB
78bR2RvMZKMDVyRi6bNY03kouSlvJGgYznfXZfsJM56o4Rq1cQru97M/LXLZT4qm
Fd5QnrFVphuQG8UPgtxbzjHZlTv8pkJjRTrojSHe1wBSKyAEsHXgfvbh4I3bPgZ6
4dVeo9c4QAwgsJBGr2DbNkJcZq1j+lED88oUlM9RAoGBAJbxMGvtfm3W68HW6Cww
wg1Np0zHOEY2IFMJqDMCPulK2UWP4L2H8HyJQB3hDVTs+9+mT0InFAHY5g2OrVaG
1c3lGw2kRgUwSrm+VIU59igtO5xYwRufv9NafSYh8SuVsIq2z6yHwPFoUe5fBPtq
E7UyzJpJlquVLMnMhcxTENYG
-----END PRIVATE KEY-----
FIREBASE_CLIENT_EMAIL=firebase-adminsdk-fbsvc@kidtech-1b497.iam.gserviceaccount.com
FIREBASE_CLIENT_ID=101111207905020928377
FIREBASE_CLIENT_X509_CERT_URL=https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40kidtech-1b497.iam.gserviceaccount.com
```

### 2. Local Development Setup

1. **Create `.env` file:**
   ```bash
   cp env.example .env
   ```

2. **Add your Firebase credentials to `.env`:**
   ```env
   FIREBASE_PROJECT_ID=kidtech-1b497
   FIREBASE_PRIVATE_KEY_ID=f8c1ece280f4c56eb8257097775373c26d986ef3
   FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCkVMiPj45ghS0T\nS2ZV1Hl+ps6LpafADekoMqpGORQ5OIYRIOdafKVFLZ2mDp0Aoa7JYERtxAooWjre\nEBqF9tDckQC9685LkcPWy2Kw+3PaHAsWjwS4EBXoT4wW1j8VWrc/vS9zq2wUl06u\nKRH51n5zuCoOGt34zghsIUzwnX7/kTukDP/OgWVLho2g3dZyL5SQ8vdPSj8mYVIh\nln7VBpOMbIAylr2jWK5V8IN1QxxKgRFR5BZSo1S/fK1ZLjXZd+t7d7A9X/uyLA71\n1pQxipQExNHA9mm+0l/jL15zundUV554Z3SXTl0J/iyTpUb8ij3GqzSMf9joirDk\nf70+oierAgMBAAECggEABHXdPgziVHISF7bV7WZ53uR5VZkGoJ0JMM6z0Z5sJYhR\nhGjugzyJK0yrYjTGw+UNTFaRKX4ib0319V/wPO80ZBqJL8MVDvbnnw6gfEngHNri\nlHK+ezCCTEo8dOkWGdSRqnry9jTJhRWPcSmYyr2IRtqs10QG2mFvjs2EBR0Tjxsa\n3fFTvy13X3hDJuIkMW5wJ3Nll4/cGVAGL0pb6sz6mPC6LhAHYV+LyXVSvxt7p0m0\nBpdE/V3XJxeGbB5inlbkCbZpjnV+iglCfa9ig1TU4nBZtEQJG56SwxNvHBuOCQ+j\npkfpyedBRqW9R4MRiiYTgV52ez5O0RfPo+Bspod54QKBgQDk7jcVXmnqBI0sYcTQ\nuRJ6zas76L5xKiQgNYyG4g1JLDVsMQx1FjTK6R3zHO8PVf8aOlYJAqHGlQaqVwVA\ncNDSXvfy4R8FPars3GwroEhfY4Nk3MDtB6lhOOWEEKoRJ/Yk+L2Xjye/Ct+CKSU9\n187zK8fgkWEweoNUSvzPUfmJFwKBgQC3wyE/UJXW//mUBtOqgLuBWtK5k6YrPIeb\nxqApswelIniVCyw+pU67ETdwC/B6GCrP0r4jV6hrVAQPzmZS44rgxnToU5dUw88E\nUTsDG9aHIpllpfPpexd2/EpcYq466TMn5CLnixWhV1YFWmoCeL/nwVZ6zCG7rU0T\nCybp9pdKjQKBgQDcAk9vut+g5iTiXUdvrB0lZdjFZ4T2bqBvT+cwjbhk9RaWVoD5\nWZD83JJK3SimHWhfxWZ/nEbq+LeCJsVGS+Vz947knRNZzw0gOym9t3k2KwXQfhLu\n+OkAJVT12aoHeNcmauKR8CMrh4CLr4055NfffNjHag/0Lhleff5+I/LjmwKBgGYB\n78bR2RvMZKMDVyRi6bNY03kouSlvJGgYznfXZfsJM56o4Rq1cQru97M/LXLZT4qm\nFd5QnrFVphuQG8UPgtxbzjHZlTv8pkJjRTrojSHe1wBSKyAEsHXgfvbh4I3bPgZ6\n4dVeo9c4QAwgsJBGr2DbNkJcZq1j+lED88oUlM9RAoGBAJbxMGvtfm3W68HW6Cww\nwg1Np0zHOEY2IFMJqDMCPulK2UWP4L2H8HyJQB3hDVTs+9+mT0InFAHY5g2OrVaG\n1c3lGw2kRgUwSrm+VIU59igtO5xYwRufv9NafSYh8SuVsIq2z6yHwPFoUe5fBPtq\nE7UyzJpJlquVLMnMhcxTENYG\n-----END PRIVATE KEY-----"
   FIREBASE_CLIENT_EMAIL=firebase-adminsdk-fbsvc@kidtech-1b497.iam.gserviceaccount.com
   FIREBASE_CLIENT_ID=101111207905020928377
   FIREBASE_CLIENT_X509_CERT_URL=https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40kidtech-1b497.iam.gserviceaccount.com
   ```

3. **Test Firebase connection:**
   ```bash
   poetry run python test_firebase.py
   ```

4. **Start development server:**
   ```bash
   poetry run python manage.py runserver
   ```

### 3. Production Deployment Options

The GitHub Actions workflow supports multiple deployment platforms:

#### Railway
Uncomment the Railway section in `.github/workflows/deploy.yml` and add:
- `RAILWAY_TOKEN` to GitHub secrets

#### Heroku
Uncomment the Heroku section and add:
- `HEROKU_API_KEY` to GitHub secrets

#### Google Cloud Run
Uncomment the Google Cloud section and add:
- `GCP_PROJECT_ID` to GitHub secrets
- `GCP_SA_KEY` to GitHub secrets

### 4. API Endpoints

Once deployed, your API will be available at:

```
POST /api/auth/verify-token/     # Verify Firebase token
GET  /api/auth/user/             # Get current user
GET  /api/auth/profile/          # Get user profile
PUT  /api/auth/profile/          # Update user profile
POST /api/auth/complete-setup/   # Complete profile setup
GET  /health/                    # Health check
```

### 5. Frontend Integration

Update your React app's API base URL to point to your deployed backend:

```javascript
// In your React app
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Example authentication request
const authenticateUser = async (firebaseToken) => {
  const response = await fetch(`${API_BASE_URL}/api/auth/verify-token/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${firebaseToken}`,
    },
    body: JSON.stringify({ token: firebaseToken }),
  });
  
  return response.json();
};
```

## 🔒 Security Notes

1. **Never commit Firebase credentials to Git**
2. **Use environment variables for all sensitive data**
3. **Rotate Firebase keys periodically**
4. **Monitor Firebase usage and authentication logs**
5. **Use HTTPS in production**

## 🐛 Troubleshooting

### Common Issues:

1. **"Firebase App named '[DEFAULT]' already exists"**
   - Restart your Django server
   - Check for duplicate Firebase initialization

2. **"Invalid authentication token"**
   - Verify Firebase credentials are correct
   - Check token expiration
   - Ensure project ID matches

3. **CORS errors**
   - Update `CORS_ALLOWED_ORIGINS` in settings
   - Add your frontend domain to allowed origins
