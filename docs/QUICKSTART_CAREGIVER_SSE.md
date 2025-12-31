# Caregiver SSE Alert Streaming - Quick Start

## What Was Added

A new SSE endpoint that allows caregivers to receive real-time alerts from **all** their patients through a **single connection**.

## New Endpoint

```http
GET /api/v1/caregivers/alerts/stream
Authorization: Bearer {jwt_token}
```

### Key Features
✅ **Automatic patient discovery** - No need to specify patient IDs  
✅ **Single connection** - Monitor all patients at once  
✅ **Real-time alerts** - Instant notification of patient issues  
✅ **Role-based access** - Only caregivers and admins  
✅ **Efficient** - Better than multiple connections per patient  

## Quick Usage

### JavaScript/Browser
```javascript
const token = 'your-jwt-token';
const eventSource = new EventSource('/api/v1/caregivers/alerts/stream', {
  headers: { 'Authorization': `Bearer ${token}` }
});

eventSource.onmessage = (event) => {
  const alert = JSON.parse(event.data);
  console.log('Alert from patient:', alert.patient_id);
  console.log('Alert type:', alert.event);
  console.log('Severity:', alert.tier);
  
  // Handle the alert in your UI
  displayAlert(alert);
};
```

### Python
```python
import requests
import json

token = "your-jwt-token"
headers = {"Authorization": f"Bearer {token}"}
url = "http://localhost:8000/api/v1/caregivers/alerts/stream"

with requests.get(url, headers=headers, stream=True) as response:
    for line in response.iter_lines():
        if line and line.startswith(b'data: '):
            alert = json.loads(line[6:])
            print(f"Alert: {alert['vital_type']} - Patient {alert['patient_id']}")
```

### Using Example Client
```bash
# Install dependencies
pip install requests

# Set your token
export CAREGIVER_TOKEN=your_jwt_token

# Run the example client
python examples/caregiver_alert_client.py
```

## Alert Format

```json
{
  "event": "alert",
  "alert_id": "abc123",
  "tier": "CRITICAL",
  "patient_id": "patient-123",
  "vital_type": "heart_rate",
  "vitals_window": [120.0, 125.0, 130.0],
  "threshold": {"min": 60.0, "max": 100.0},
  "reasons": ["heart_rate outside 60-100 for 3 samples"],
  "recipients": ["caregiver"],
  "timestamp": "2025-12-29T23:30:00Z"
}
```

## Acknowledge Alerts

```bash
curl -X POST \
  "http://localhost:8000/api/v1/alerts/alerts/{alert_id}/acknowledge?patient_id={patient_id}" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "resolved", "note": "Patient contacted"}'
```

## Testing

All tests pass ✅

```bash
# Run all alert tests
uv run pytest tests/modules/alerts/ -v

# Run only caregiver SSE tests
uv run pytest tests/modules/alerts/test_sse_router.py::TestCaregiverSSEStream -v
```

## Documentation

📖 **Full Documentation:** `docs/caregiver-alert-streaming.md`  
📝 **Implementation Summary:** `docs/IMPLEMENTATION_SUMMARY_CAREGIVER_SSE.md`  
💻 **Example Client:** `examples/caregiver_alert_client.py`

## Architecture

```
┌─────────────┐
│  Caregiver  │
│   Client    │
└──────┬──────┘
       │ SSE Connection
       │ GET /api/v1/caregivers/alerts/stream
       ▼
┌─────────────────────────────────────┐
│   Alert Router                      │
│   - Verify CAREGIVER role           │
│   - Fetch patient list              │
│   - Subscribe to all patient alerts │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│   Alert Connection Manager          │
│   - Multi-patient subscriptions     │
│   - Queue-based delivery            │
│   - Efficient cleanup               │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│   Alert Engine                      │
│   - Processes vital data            │
│   - Triggers alerts                 │
│   - Broadcasts to subscribers       │
└─────────────────────────────────────┘
```

## Benefits

### For Caregivers
- 👀 Monitor all patients from one screen
- ⚡ Instant notifications of critical events
- 📱 Works in browsers and mobile apps
- 🔄 Automatic reconnection on disconnect

### For Developers
- 🎯 Simple API - no complex parameters
- 🧪 Well-tested - 25 tests all passing
- 📚 Comprehensive documentation
- 🔧 Example code provided

### For System
- 💪 Efficient - one connection vs many
- 🔒 Secure - role-based access control
- 📈 Scalable - queue-based architecture
- ♻️ Clean - proper resource cleanup

## Next Steps

1. **Try the example client** to see it in action
2. **Read the full documentation** for advanced features
3. **Integrate into your frontend** using the code examples
4. **Test with your caregivers** to gather feedback

## Support

- 📖 See `docs/caregiver-alert-streaming.md` for detailed info
- 🐛 Check server logs for debugging
- ✅ Verify caregiver has patient access relationships
- 🔑 Ensure JWT token is valid and not expired
