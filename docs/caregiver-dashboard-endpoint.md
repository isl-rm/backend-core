# Caregiver Dashboard Endpoint

## Overview
Added a new HTTP endpoint that allows caregivers to view the vitals dashboard summary for their patients.

## Endpoint Details

### GET `/api/v1/caregivers/patients/{patient_id}/dashboard`

**Description:** Returns the latest vitals dashboard summary for a specific patient.

**Authentication:** Required (Bearer token)

**Authorization:** User must have the `CAREGIVER` role and active access to the specified patient.

**Path Parameters:**
- `patient_id` (string, required): The ID of the patient whose dashboard to retrieve

**Response Model:** `DashboardSummary`

**Response Example:**
```json
{
  "status": "ok",
  "statusNote": "Latest vitals available",
  "lastUpdated": "2025-12-29T19:23:36Z",
  "vitals": {
    "ecg": "0",
    "bloodPressure": "120/80 mmHg",
    "heartRate": 75.0,
    "spo2": 98.0,
    "temperatureC": 0.0,
    "respRate": 0.0,
    "bloodSugar": 0.0,
    "weightKg": 0.0
  }
}
```

**Error Responses:**
- `403 Forbidden`: Caregiver does not have access to this patient's data
- `404 Not Found`: Patient not found
- `401 Unauthorized`: Invalid or missing authentication token

## Implementation Details

### Files Modified
1. **`app/modules/caregivers/vitals/router.py`**
   - Added new HTTP GET endpoint `read_patient_dashboard_summary`
   - Imports: Added `HTTPException`, `DashboardSummary`, `VitalService`, and `deps`

2. **`app/modules/caregivers/router.py`**
   - Registered the vitals router with the main caregivers router

### Access Control
The endpoint implements proper access control by:
1. Verifying the user has the `CAREGIVER` role (via `deps.RoleChecker`)
2. Checking that the caregiver has active access to the requested patient
3. Returning 403 Forbidden if access is not granted

### Service Reuse
The endpoint reuses the existing `VitalService.get_dashboard_summary()` method, ensuring consistency with the patient's own dashboard view.

## Testing

Created comprehensive tests in `tests/modules/caregivers/test_vitals_router.py`:

1. ✅ `test_caregiver_can_view_patient_dashboard` - Verifies authorized access
2. ✅ `test_caregiver_cannot_view_unauthorized_patient_dashboard` - Verifies access control
3. ✅ `test_patient_cannot_view_dashboard_via_caregiver_endpoint` - Verifies role-based access
4. ✅ `test_caregiver_dashboard_returns_empty_when_no_vitals` - Verifies empty state handling

All tests passing ✓

## Usage Example

```python
import httpx

# Authenticate as caregiver
token = "caregiver_access_token"
patient_id = "507f1f77bcf86cd799439011"

# Request patient dashboard
response = httpx.get(
    f"http://localhost:8000/api/v1/caregivers/patients/{patient_id}/dashboard",
    headers={"Authorization": f"Bearer {token}"}
)

if response.status_code == 200:
    dashboard = response.json()
    print(f"Patient vitals: {dashboard['vitals']}")
elif response.status_code == 403:
    print("Access denied - no permission for this patient")
```
