# PowerShell API Test Script
Write-Host "Testing the fixed leave-requests endpoint..." -ForegroundColor Green

try {
    # Login to get token
    Write-Host "1. Testing login..." -ForegroundColor Yellow
    $loginResponse = Invoke-RestMethod -Uri "http://127.0.0.1:8000/login" -Method Post -ContentType "application/json" -Body '{"username":"10001","password":"test@123"}'
    $token = $loginResponse.access_token
    Write-Host "   ✓ Login successful!" -ForegroundColor Green
    
    # Test the leave requests endpoint that was failing
    Write-Host "2. Testing leave-requests endpoint..." -ForegroundColor Yellow
    $headers = @{Authorization = "Bearer $token"}
    $leaveResponse = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/leave-requests/10001" -Method Get -Headers $headers
    
    Write-Host "   ✓ Leave requests endpoint working!" -ForegroundColor Green
    Write-Host "   Response: $($leaveResponse | ConvertTo-Json -Depth 2)" -ForegroundColor Cyan
    
    Write-Host "`n✓ All tests passed! The 500 error is fixed!" -ForegroundColor Green
    
} catch {
    Write-Host "❌ Error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`nPress any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")