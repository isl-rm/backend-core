# Caregiver Alert Streaming via SSE

## Overview

This document describes the new Server-Sent Events (SSE) endpoint that allows caregivers to receive real-time alerts from all patients they have access to through a single connection.

## Endpoint

### `GET /api/v1/caregivers/alerts/stream`

Stream alerts from all patients that the authenticated caregiver has access to.

**Authentication:** Required (Bearer token)

**Required Role:** `CAREGIVER` or `ADMIN`

**Response:** Server-Sent Events stream (`text/event-stream`)

## Features

### Automatic Patient Discovery
- The endpoint automatically fetches all patients the caregiver has access to
- No need to specify individual patient IDs
- Dynamically subscribes to alerts from all authorized patients

### Multi-Patient Support
- Single connection receives alerts from all subscribed patients
- Efficient subscription management for multiple patients
- Proper cleanup when connection closes

### Role-Based Access Control
- Only users with `CAREGIVER` or `ADMIN` roles can access this endpoint
- Respects existing `CaregiverPatientAccess` relationships
- Automatically enforces access permissions

### Graceful Handling
- Works even when caregiver has no patients yet
- Sends keepalive messages every 30 seconds to maintain connection
- Automatic reconnection support via SSE protocol

## Usage Example

### JavaScript/TypeScript Client

```typescript
const token = 'your-jwt-token';

const eventSource = new EventSource(
  '/api/v1/caregivers/alerts/stream',
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);

eventSource.onmessage = (event) => {
  const alert = JSON.parse(event.data);
  console.log('Received alert:', alert);
  
  // Handle different alert types
  switch (alert.event) {
    case 'alert':
      handleNewAlert(alert);
      break;
    case 'alert_escalated':
      handleEscalatedAlert(alert);
      break;
    case 'ack':
      handleAlertAcknowledgment(alert);
      break;
  }
};

eventSource.onerror = (error) => {
  console.error('SSE connection error:', error);
  // EventSource will automatically attempt to reconnect
};

// Close connection when done
eventSource.close();
```

### Python Client

```python
import requests
import json

token = "your-jwt-token"
headers = {"Authorization": f"Bearer {token}"}

url = "http://localhost:8000/api/v1/caregivers/alerts/stream"

with requests.get(url, headers=headers, stream=True) as response:
    response.raise_for_status()
    
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            
            # Skip keepalive comments
            if decoded_line.startswith(':'):
                continue
                
            # Parse SSE data
            if decoded_line.startswith('data: '):
                alert_data = json.loads(decoded_line[6:])
                print(f"Received alert: {alert_data}")
                
                # Process alert
                handle_alert(alert_data)
```

## Alert Event Format

### New Alert Event
```json
{
  "event": "alert",
  "alert_id": "abc123def456",
  "tier": "CRITICAL",
  "patient_id": "patient-id-123",
  "vital_type": "heart_rate",
  "vitals_window": [120.0, 125.0, 130.0],
  "threshold": {
    "min": 60.0,
    "max": 100.0
  },
  "reasons": ["heart_rate outside 60-100 for 3 samples"],
  "recipients": ["caregiver"],
  "timestamp": "2025-12-29T23:30:00Z",
  "context": {
    "age": 65,
    "additional_info": "..."
  }
}
```

### Escalated Alert Event
```json
{
  "event": "alert_escalated",
  "alert_id": "abc123def456",
  "tier": "CRITICAL",
  "patient_id": "patient-id-123",
  "vital_type": "heart_rate",
  "vitals_window": [120.0, 125.0, 130.0],
  "threshold": {
    "min": 60.0,
    "max": 100.0
  },
  "reasons": ["heart_rate outside 60-100 for 3 samples"],
  "recipients": ["doctor", "nurse"],
  "timestamp": "2025-12-29T23:35:00Z"
}
```

### Acknowledgment Event
```json
{
  "event": "ack",
  "alert_id": "abc123def456",
  "patient_id": "patient-id-123",
  "tier": "CRITICAL",
  "timestamp": "2025-12-29T23:31:00Z",
  "acknowledged_by": "patient",
  "status": "resolved",
  "note": "Patient is stable"
}
```

## Acknowledging Alerts

Caregivers can acknowledge alerts using the HTTP POST endpoint:

```http
POST /api/v1/alerts/alerts/{alert_id}/acknowledge?patient_id={patient_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "status": "resolved",
  "note": "Contacted patient, vitals normalized"
}
```

## Architecture

### Connection Flow

1. **Authentication**: User authenticates with JWT token
2. **Role Verification**: System verifies user has `CAREGIVER` or `ADMIN` role
3. **Patient Discovery**: System fetches all patients the caregiver has access to via `CaregiverPatientAccess`
4. **Multi-Patient Subscription**: Alert manager subscribes the connection to all patient alert streams
5. **Alert Delivery**: When any subscribed patient triggers an alert, it's sent to the caregiver's SSE stream
6. **Cleanup**: On disconnect, all subscriptions are properly cleaned up

### Key Components

#### `AlertConnectionManager`
- Manages SSE subscriptions for multiple patients
- `subscribe_sse_for_patients()`: Registers a queue for alerts from multiple patients
- Tracks caregiver subscriptions for efficient cleanup
- Prevents duplicate alert delivery

#### `CaregiverPatientService`
- `list_patient_ids()`: Fetches all active patient IDs for a caregiver
- Respects `CaregiverPatientAccess.active` flag
- Returns empty list if no patients (graceful handling)

## Comparison with Single-Patient Endpoint

### `/api/v1/alerts/stream` (Single Patient)
- Requires `role` and `patient_id` query parameters
- Subscribes to alerts for one specific patient
- Used by patients, doctors, nurses for specific patient monitoring

### `/api/v1/caregivers/alerts/stream` (Multi-Patient)
- No query parameters needed
- Automatically subscribes to all caregiver's patients
- Specifically designed for caregivers managing multiple patients
- More efficient than opening multiple connections

## Error Handling

### 401 Unauthorized
- Missing or invalid authentication token
- **Solution**: Provide valid JWT token in Authorization header

### 403 Forbidden
- User does not have `CAREGIVER` or `ADMIN` role
- **Solution**: Ensure user has appropriate role assigned

### Connection Drops
- Network issues or server restart
- **Solution**: SSE protocol automatically attempts to reconnect
- Client should implement reconnection logic with exponential backoff

## Performance Considerations

### Queue Management
- Each SSE connection has a queue with max size of 100 alerts
- If queue fills (slow client), new alerts are dropped
- Keepalive messages sent every 30 seconds to maintain connection

### Subscription Efficiency
- Caregiver subscriptions are tracked separately for efficient cleanup
- Single queue receives alerts from all patients
- No duplicate subscriptions per patient

### Scalability
- Consider using Redis Pub/Sub for multi-server deployments
- Current implementation is in-memory (single server)
- For production, implement distributed alert manager

## Testing

Comprehensive test suite covers:
- ✅ Successful streaming with single patient
- ✅ Successful streaming with multiple patients
- ✅ Graceful handling when caregiver has no patients
- ✅ Role-based access control (unauthorized users rejected)
- ✅ Admin access to endpoint
- ✅ Unauthenticated requests rejected
- ✅ Proper subscription cleanup on disconnect

Run tests:
```bash
uv run pytest tests/modules/alerts/test_sse_router.py::TestCaregiverSSEStream -v
```

## Migration from WebSocket

If you're currently using WebSocket for alerts, consider migrating to SSE:

### Benefits of SSE
- Simpler protocol (HTTP-based)
- Automatic reconnection built into browser EventSource API
- Better firewall/proxy compatibility
- Lower overhead than WebSocket for one-way communication

### Migration Steps
1. Update client to use EventSource instead of WebSocket
2. Change acknowledgments to use HTTP POST endpoint
3. Test thoroughly in staging environment
4. Deploy with backward compatibility (WebSocket still supported)

## Security Considerations

### Authentication
- All requests must include valid JWT token
- Token validated on every connection attempt
- User status must be `ACTIVE`

### Authorization
- Only caregivers with active `CaregiverPatientAccess` receive alerts
- Revoking access immediately stops alert delivery on next connection
- Admin users can access endpoint but may have no patients

### Data Privacy
- Alerts only sent to authorized caregivers
- Patient data included in alerts (ensure HIPAA compliance)
- Consider encrypting sensitive fields in production

## Future Enhancements

### Potential Improvements
- [ ] Filter alerts by severity level
- [ ] Support for alert history on connection
- [ ] Batch acknowledgments for multiple alerts
- [ ] Alert statistics and analytics
- [ ] Push notifications integration
- [ ] Dynamic patient list updates (when caregiver gains/loses access)
- [ ] Redis-based distributed alert manager for horizontal scaling

## Support

For issues or questions:
- Check server logs for detailed error messages
- Verify caregiver has active patient access relationships
- Ensure JWT token is valid and not expired
- Test with single patient first before scaling to multiple
