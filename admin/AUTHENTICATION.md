# Admin Authentication System

## Overview
The PagePay admin panel uses JWT-based authentication with the backend API.

## Backend Endpoints

### Login
```
POST /api/v1/admin/auth/login
```

**Request:**
```json
{
  "email": "admin@pagepay.app",
  "password": "admin123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "role": "super_admin",
  "permissions": ["*"]
}
```

### Get Current Admin
```
GET /api/v1/admin/auth/me
Authorization: Bearer {token}
```

**Response:**
```json
{
  "id": 1,
  "email": "admin@pagepay.app",
  "role": "super_admin",
  "is_active": true,
  "last_login_at": "2026-07-01T10:30:00Z",
  "created_at": "2026-06-01T00:00:00Z"
}
```

## Default Admin Credentials

The seed script creates a default super admin:

- **Email:** `admin@pagepay.app` (override with `PAGEADMIN_EMAIL`)
- **Password:** `admin123` (override with `PAGEADMIN_PASSWORD`)
- **Role:** `super_admin`
- **Permissions:** All (`["*"]`)

⚠️ **Security:** Change these credentials immediately in production!

## Frontend Implementation

### API Configuration
- **Base URL:** `http://localhost:8000/api/v1` (configurable via `VITE_API_URL`)
- **Token Storage:** localStorage (`admin_token` key)
- **Auto-injection:** Bearer token added to all requests
- **Auto-logout:** 401 responses clear token and redirect to login

### Authentication Flow

1. User enters email/password on `/login`
2. Frontend calls `POST /api/v1/admin/auth/login`
3. Backend validates credentials and returns JWT token
4. Frontend stores token in localStorage and Zustand store
5. Frontend redirects to `/dashboard`
6. All subsequent API calls include `Authorization: Bearer {token}` header

### Permission System

The frontend implements permission checking via `useAuthStore`:

```typescript
const hasPermission = useAuthStore((s) => s.hasPermission);

if (hasPermission('users.ban')) {
  // Show ban user button
}
```

**Rules:**
- Super admins (`role === 'super_admin'`) have all permissions
- Admins with `*` in their permissions array have all permissions
- Other admins must have the specific permission in their array

## Testing Locally

1. **Start the backend:**
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

2. **Start the admin frontend:**
   ```bash
   cd admin
   npm run dev
   ```

3. **Login:**
   - Navigate to `http://localhost:5173/login`
   - Email: `admin@pagepay.app`
   - Password: `admin123`

## Creating Additional Admins

There is **no public registration endpoint** for security reasons. To create new admins:

### Option 1: Direct Database Insert
```sql
INSERT INTO admin_users (email, password_hash, role, permissions, is_active)
VALUES (
  'new.admin@pagepay.app',
  '$2b$12$...',  -- Use bcrypt to hash the password
  'admin',
  '["users.view", "content.view"]',
  1
);
```

### Option 2: Python Script
```python
from app.services.admin_auth import hash_password
from app.models import AdminUser
import json

# In a migration or script
admin = AdminUser(
    email="new.admin@pagepay.app",
    password_hash=hash_password("secure_password"),
    role="admin",
    permissions=json.dumps(["users.view", "content.view"]),
    is_active=True
)
db.add(admin)
db.commit()
```

### Option 3: Admin Management UI (TODO)
Consider adding admin user management endpoints for super admins:
- `POST /api/v1/admin/users` - Create new admin
- `GET /api/v1/admin/users` - List all admins
- `PUT /api/v1/admin/users/{id}` - Update admin
- `DELETE /api/v1/admin/users/{id}` - Deactivate admin

## Available Permissions

Based on the backend implementation, here are the permission strings:

### Dashboard
- `dashboard.view` - View dashboard stats

### Users
- `users.view` - View user list and details
- `users.ban` - Ban/unban users
- `users.adjust_balance` - Adjust user points balance

### Finance
- `finance.view` - View revenue and payout data
- `finance.approve` - Approve/reject payouts

### Content
- `content.view` - View content catalog
- `content.delete` - Delete content

### Fraud Detection
- `fraud.view` - View fraud flags

### AI Monitoring
- `ai.view` - View AI provider health

### Configuration
- `config.view` - View app configuration
- `config.edit` - Update app configuration

### Audit Logs
- `logs.view` - View audit logs

### Analytics
- `analytics.view` - View analytics data

### Tasks (Phase 7)
- `tasks.kyc` - Review and approve/reject sponsor KYC

## Security Notes

1. **Password Hashing:** Passwords are hashed using bcrypt with auto-generated salt
2. **JWT Expiration:** Tokens expire based on `ACCESS_TOKEN_EXPIRE_MINUTES` (default: varies by environment)
3. **CORS:** Backend validates CORS origins from `settings.cors_origins_list`
4. **Rate Limiting:** Login endpoint may have rate limiting (check `app/limiter.py`)
5. **HTTPS:** Always use HTTPS in production to protect tokens in transit

## Troubleshooting

### "Invalid credentials" error
- Verify email/password are correct
- Check that admin user exists in database
- Ensure `is_active` is `true` in database

### "Could not validate admin credentials"
- Token may be expired - log in again
- Token may be malformed - clear localStorage and log in again
- `SECRET_KEY` in backend may have changed

### CORS errors
- Ensure admin frontend URL is in backend's `CORS_ORIGINS` environment variable
- Default: `http://localhost:5173,http://localhost:3000`

### 401 on protected routes
- Ensure token is being sent in Authorization header
- Check browser DevTools Network tab for the header
- Token may have expired - the frontend should auto-redirect to login
