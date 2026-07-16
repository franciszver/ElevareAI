# Troubleshooting API Connection Issues

## Quick Checks

### 1. Is the backend running?
```powershell
# Check if something is listening on port 8000
netstat -ano | findstr :8000

# Test health endpoint
Invoke-WebRequest -Uri "http://localhost:8000/health"
```

### 2. Check Browser Console
Open your browser's Developer Tools (F12) and check:
- **Console tab**: Look for API errors
- **Network tab**: Check if requests are being made and what status codes they return

### 3. Common Issues

#### Issue: "API calls are failing" message
**Possible causes:**
1. Backend not running - Start with `.\START_SERVER.ps1`
2. Wrong user_id format - Should be UUID like `180bcad6-380e-4a2f-809b-032677fcc721`
3. CORS issue - Check browser console for CORS errors
4. Authentication issue - Check if a valid access token is being sent

#### Issue: 401 Unauthorized
- Check if `auth_token` is in localStorage
- Check browser console for token being sent
- Verify the token was issued by `/api/v1/auth/login` and hasn't expired

#### Issue: 404 Not Found
- Check if user_id is correct UUID
- Verify demo accounts exist: `python scripts/verify_demo_users.py`
- Check API endpoint URL is correct

#### Issue: 422 Unprocessable Entity
- Usually means UUID format is invalid
- Check browser console for exact error message
- Verify user_id is a valid UUID string

## Debug Steps

### Step 1: Verify Backend is Running
```powershell
# Start server
.\START_SERVER.ps1

# In another terminal, test it
Invoke-WebRequest -Uri "http://localhost:8000/health"
```

### Step 2: Check Frontend Console
1. Open browser DevTools (F12)
2. Go to Console tab
3. Look for errors starting with `[DASHBOARD]` or `[API]`
4. Check Network tab to see actual HTTP requests

### Step 3: Test API Directly
```powershell
# Log in with demo credentials to get an access token
$loginBody = @{ email = "demo@demo.com"; password = "demo-password" } | ConvertTo-Json
$loginResp = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
$headers = @{
    "Authorization" = "Bearer $($loginResp.access_token)"
}

# Test progress endpoint
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/progress/180bcad6-380e-4a2f-809b-032677fcc721" -Headers $headers
```

### Step 4: Verify User ID
1. Login with demo account
2. Open browser console
3. Type: `localStorage.getItem('user_id')`
4. Should show UUID like: `180bcad6-380e-4a2f-809b-032677fcc721`

## Expected Console Output

When working correctly, you should see:
```
[AUTH] Login called with email: demo_goal_complete@demo.com
[AUTH] Received access_token and userId: { userId: '180bcad6-380e-4a2f-809b-032677fcc721' }
[DASHBOARD] Fetching progress for user: 180bcad6-380e-4a2f-809b-032677fcc721
[DASHBOARD] Progress response: { success: true, data: {...} }
```

## Still Not Working?

1. **Clear browser cache and localStorage:**
   ```javascript
   // In browser console
   localStorage.clear()
   location.reload()
   ```

2. **Restart both frontend and backend:**
   - Stop backend: `.\STOP_SERVER.ps1`
   - Start backend: `.\START_SERVER.ps1`
   - Restart frontend dev server

3. **Check for multiple server instances:**
   ```powershell
   # Kill all processes on port 8000
   .\STOP_SERVER.ps1
   ```

4. **Verify demo accounts exist:**
   ```powershell
   python scripts/verify_demo_users.py
   ```

