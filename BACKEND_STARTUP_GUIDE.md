# Backend Startup Guide - PagePay

## Prerequisites

Before starting the backend, ensure:
- Docker is installed and running
- MySQL is accessible (via Docker)
- Python 3.11+ available (for development)
- Backend environment variables configured

---

## Quick Start (Docker Compose)

### Step 1: Navigate to Backend Directory
```bash
cd backend
```

### Step 2: Start Backend Services
```bash
docker-compose restart
```

This will:
- ✅ Start the FastAPI backend on `http://localhost:8000`
- ✅ Start MySQL database (if not running)
- ✅ Run database migrations
- ✅ Seed admin users

### Step 3: Verify Backend is Running
```bash
curl http://localhost:8000/health
```

**Expected response** (200 OK):
```json
{"status": "ok", "timestamp": "2026-07-03T..."}
```

### Step 4: Test Admin Login Endpoint
```bash
curl -X POST http://localhost:8000/api/v1/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@pagepay.dev",
    "password": "your_password"
  }'
```

---

## Common Issues & Fixes

### Issue 1: Backend Returns 404 Errors

**Symptoms**:
```
Failed to load resource: the server responded with a status of 404 (Not Found)
api/v1/admin/auth/login:1
```

**Cause**: Backend is not running or not accessible at `localhost:8000`

**Fix**:
```bash
# Ensure backend is running
cd backend
docker-compose up -d

# Check if it's running
docker-compose logs -f fastapi
```

**Expected output**:
```
fastapi_1  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Issue 2: Database Connection Error

**Symptoms**:
```
sqlalchemy.exc.OperationalError: (pymysql.err.OperationalError) ...
```

**Cause**: MySQL is not running or wrong credentials

**Fix**:
```bash
# Check MySQL is running
docker-compose logs mysql

# Restart MySQL
docker-compose restart mysql

# Check .env file has correct credentials
cat .env
```

### Issue 3: Port Already in Use

**Symptoms**:
```
ERROR: for pagepay_fastapi  Cannot start service fastapi: ... port 8000 already in use
```

**Fix**:
```bash
# Kill process on port 8000 (or change port in docker-compose.yml)
# On Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Or use different port in docker-compose.yml:
# Change "8000:8000" to "8001:8000"
```

### Issue 4: React Can't Connect to Backend

**Symptoms**:
```
Failed to load resource: the server responded with a status of 404 (Not Found)
```

**Cause**: Vite proxy not working or backend not at `localhost:8000`

**Fix**:
1. Ensure backend is at `http://localhost:8000`:
   ```bash
   cd backend && docker-compose logs
   ```

2. Check vite.config.ts has correct proxy:
   ```typescript
   // admin/vite.config.ts
   server: {
     port: 3000,
     proxy: {
       '/api': {
         target: 'http://localhost:8000',
         changeOrigin: true,
       },
     },
   }
   ```

3. Restart admin dev server:
   ```bash
   cd admin
   npm run dev
   ```

---

## Starting Individual Services

### Option 1: Docker Compose (Recommended)
```bash
cd backend
docker-compose up -d
```

### Option 2: Local Development (Without Docker)

#### Prerequisites
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Set up MySQL connection in .env
# DB_URL=mysql+aiomysql://root:password@localhost:3306/pagepay
```

#### Run Backend
```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

**Expected output**:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

---

## Environment Configuration

### Required Variables (.env)

```bash
# Database
DB_URL=mysql+aiomysql://root:pagepay_local@mysql:3306/pagepay

# JWT
SECRET_KEY=your_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Admin Defaults
DEFAULT_ADMIN_EMAIL=admin@pagepay.dev
DEFAULT_ADMIN_PASSWORD=pagepay_admin_local

# Paystack (for refunds)
PAYSTACK_SECRET_KEY=pk_test_xxxxx...
PAYSTACK_PUBLIC_KEY=pk_test_xxxxx...

# CORS Origins
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Other services
REDIS_URL=redis://redis:6379/0  # Optional
LOG_LEVEL=INFO
```

### Check Current Configuration
```bash
cat backend/.env
```

---

## Verifying Routes

### Test All Admin Routes Are Registered

1. **Auth Routes**:
   ```bash
   POST /api/v1/admin/auth/login
   GET /api/v1/admin/auth/me
   POST /api/v1/admin/auth/logout
   ```

2. **User Management Routes**:
   ```bash
   GET /api/v1/admin/admins
   POST /api/v1/admin/admins
   GET /api/v1/admin/admins/{admin_id}
   ```

3. **Payment Routes** (NEW):
   ```bash
   GET /api/v1/admin/payments/subscriptions
   GET /api/v1/admin/payments/subscriptions/{payment_id}
   POST /api/v1/admin/payments/subscriptions/{payment_id}/refund
   GET /api/v1/admin/payments/failed
   GET /api/v1/admin/payments/subscriptions/active
   ```

4. **All Other Routes**:
   ```bash
   GET /api/v1/admin/fraud/flags
   GET /api/v1/admin/finance/revenue
   POST /api/v1/admin/payouts/{payout_id}/approve
   # ... and 70+ more
   ```

### Quick Test Script
```bash
#!/bin/bash
# test-backend.sh

echo "Testing backend at localhost:8000"
echo "=================================="

# Test health
echo "1. Health check..."
curl -s http://localhost:8000/health | jq '.'

# Test auth endpoint exists
echo -e "\n2. Auth endpoint..."
curl -s -X POST http://localhost:8000/api/v1/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@pagepay.dev","password":"invalid"}' | jq '.detail'

# Test payment endpoints
echo -e "\n3. Payment endpoints exist..."
curl -s -H "Authorization: Bearer test_token" \
  http://localhost:8000/api/v1/admin/payments/subscriptions | jq '.detail // "No error"'

echo -e "\n✅ Backend is responding"
```

---

## Docker Compose Reference

### Start All Services
```bash
docker-compose up -d
```

### Stop All Services
```bash
docker-compose down
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f fastapi
docker-compose logs -f mysql
```

### Restart Specific Service
```bash
docker-compose restart fastapi
```

### Rebuild Images
```bash
docker-compose build --no-cache
```

---

## Frontend Setup (After Backend is Running)

### Admin Panel
```bash
cd admin
npm install  # if not already done
npm run dev
```

**Open browser**: http://localhost:3000

**Login with**:
- Email: `admin@pagepay.dev`
- Password: `pagepay_admin_local`

---

## Troubleshooting Checklist

- [ ] Backend running on `http://localhost:8000`
- [ ] MySQL running and accessible
- [ ] Environment variables configured in `.env`
- [ ] Database migrations completed
- [ ] Admin user seeded in database
- [ ] Health endpoint responds: `curl http://localhost:8000/health`
- [ ] Auth endpoint responds: `curl -X POST http://localhost:8000/api/v1/admin/auth/login ...`
- [ ] Admin panel frontend at `http://localhost:3000`
- [ ] Browser console has no CORS errors
- [ ] Vite proxy configured to `http://localhost:8000`

---

## Common Ports

| Service | Port | URL |
|---------|------|-----|
| Backend (FastAPI) | 8000 | http://localhost:8000 |
| Admin Panel (React) | 3000 | http://localhost:3000 |
| MySQL | 3306 | localhost:3306 |
| Redis (optional) | 6379 | localhost:6379 |

---

## Performance Tips

### Database Optimization
```bash
# Check slow queries
docker-compose exec mysql mysql -u root -p -e "SHOW PROCESSLIST;"
```

### API Response Times
```bash
# Monitor with curl timing
curl -w "Time: %{time_total}s\n" http://localhost:8000/health
```

### Docker Resource Usage
```bash
# Check memory/CPU
docker stats
```

---

## Production Deployment

For deployment to production, see:
- `.kilo/agent/devops.md` - DevOps guidelines
- `roadmap.md` - Deployment architecture

---

**Status**: Backend Architecture Ready ✅  
**Last Updated**: July 3, 2026  
**For Issues**: Check ROUTE_VERIFICATION_2026.md or PROJECT_STATUS_JULY_2026.md
