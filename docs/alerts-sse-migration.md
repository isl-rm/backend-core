# Alert Notifications: WebSocket to SSE Migration Guide

## Overview

This document describes the migration from WebSocket to Server-Sent Events (SSE) for alert notifications in the backend-core system. Both protocols are supported during the transition period to ensure backward compatibility.

## Architecture Decision

### Why SSE for Alerts?

**Server-Sent Events (SSE)** is the recommended approach for alert notifications because:

1. **Unidirectional Communication**: Alerts flow server → client only. SSE is optimized for this pattern.
2. **Automatic Reconnection**: Built-in reconnection logic in the browser's `EventSource` API.
3. **Better Infrastructure Compatibility**: Works better with proxies, load balancers, and CDNs.
4. **Simpler Client Code**: `EventSource` is easier to use than WebSocket.
5. **HTTP/2 Multiplexing**: Can share connections with other HTTP traffic.

### Why Keep WebSocket for Vitals?

**WebSocket** remains the best choice for vital signs streaming because:

1. **High-Frequency Data**: ECG samples at 100-500 Hz require low overhead.
2. **Bidirectional Pattern**: Mobile app sends data, backend broadcasts to frontend.
3. **Binary Support**: More efficient for large data payloads.
4. **Lower Latency**: Critical for real-time ECG visualization.

---

## API Endpoints

### SSE Streaming Endpoint (New - Recommended)

**Endpoint**: `GET /api/v1/alerts/stream`

**Authentication**: Bearer token (via Authorization header or cookie)

**Query Parameters**:
- `role` (required): User role (`caregiver`, `doctor`, `nurse`, `dispatcher`, `admin`, `patient`)
- `patient_id` (optional): Patient ID to monitor
  - Required for non-admin roles
  - Use `*` or `all` for admin to monitor all patients
  - Automatically set to user's ID for `patient` role

**Response**: `text/event-stream`

**Example Request**:
```bash
curl -N -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/api/v1/alerts/stream?role=caregiver&patient_id=123"
```

**Example Response**:
```
data: {"event":"alert","alertId":"abc123","tier":"CRITICAL","patientId":"123","vitalType":"heart_rate","vitalsWindow":[120,125,130],"threshold":{"min":60,"max":100},"reasons":["heart_rate outside 60-100 for 3 samples"],"recipients":["caregiver"],"timestamp":"2025-12-29T19:40:00Z","source":"mock_ai"}

data: {"event":"alert_escalated","alertId":"abc123","tier":"CRITICAL","patientId":"123","vitalType":"heart_rate","vitalsWindow":[120,125,130],"threshold":{"min":60,"max":100},"reasons":["heart_rate outside 60-100 for 3 samples"],"recipients":["doctor"],"timestamp":"2025-12-29T19:45:00Z","source":"mock_ai"}

: keepalive
```

**Features**:
- Automatic keepalive messages every 30 seconds
- Graceful disconnect detection
- Queue-based message delivery (max 100 pending messages)
- Proper SSE headers (no-cache, keep-alive, no buffering)

---

### HTTP Acknowledgment Endpoint (New - For SSE Clients)

**Endpoint**: `POST /api/v1/alerts/alerts/{alert_id}/acknowledge`

**Authentication**: Bearer token (via Authorization header or cookie)

**Path Parameters**:
- `alert_id` (required): The alert ID to acknowledge

**Query Parameters**:
- `patient_id` (required): The patient ID associated with the alert

**Request Body**:
```json
{
  "status": "resolved",  // Optional: acknowledgment status
  "note": "Patient contacted and stable"  // Optional: note from user
}
```

**Response** (200 OK):
```json
{
  "message": "Alert acknowledged successfully",
  "alertId": "abc123"
}
```

**Error Responses**:
- `401 Unauthorized`: Missing or invalid authentication
- `403 Forbidden`: User has no valid role for acknowledgment
- `404 Not Found`: Alert not found or already acknowledged

**Example Request**:
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"resolved","note":"Patient is stable"}' \
  "http://localhost:8000/api/v1/alerts/alerts/abc123/acknowledge?patient_id=123"
```

---

### WebSocket Endpoint (Legacy - Backward Compatibility)

**Endpoint**: `WS /api/v1/alerts/ws`

**Query Parameters**:
- `token` (required): JWT authentication token
- `role` (required): User role
- `patient_id` (optional): Patient ID to monitor

**Maintained for backward compatibility during migration.**

---

## Client Implementation

### JavaScript/TypeScript (SSE)

```typescript
// Connect to SSE stream
const token = localStorage.getItem('access_token');
const patientId = '123';
const role = 'caregiver';

const eventSource = new EventSource(
  `/api/v1/alerts/stream?role=${role}&patient_id=${patientId}`,
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);

// Handle incoming alerts
eventSource.onmessage = (event) => {
  const alert = JSON.parse(event.data);
  
  switch (alert.event) {
    case 'alert':
      console.log('New alert:', alert);
      showAlertNotification(alert);
      break;
      
    case 'alert_escalated':
      console.log('Alert escalated:', alert);
      showEscalationNotification(alert);
      break;
      
    case 'alert_acknowledged':
      console.log('Alert acknowledged:', alert);
      updateAlertStatus(alert);
      break;
  }
};

// Handle errors (will auto-reconnect)
eventSource.onerror = (error) => {
  console.error('SSE error:', error);
  // EventSource will automatically attempt to reconnect
};

// Acknowledge an alert
async function acknowledgeAlert(alertId: string, patientId: string) {
  const response = await fetch(
    `/api/v1/alerts/alerts/${alertId}/acknowledge?patient_id=${patientId}`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        status: 'resolved',
        note: 'Patient contacted and stable'
      })
    }
  );
  
  if (!response.ok) {
    throw new Error('Failed to acknowledge alert');
  }
  
  return response.json();
}

// Clean up on unmount
eventSource.close();
```

### Python (SSE Client)

```python
import httpx
import json

async def stream_alerts(token: str, role: str, patient_id: str):
    headers = {"Authorization": f"Bearer {token}"}
    params = {"role": role, "patient_id": patient_id}
    
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "GET",
            "http://localhost:8000/api/v1/alerts/stream",
            headers=headers,
            params=params,
            timeout=None,
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    print(f"Received alert: {data}")
                    
                    # Process alert
                    if data["event"] == "alert":
                        await handle_new_alert(data)

async def acknowledge_alert(
    token: str,
    alert_id: str,
    patient_id: str,
    status: str = None,
    note: str = None
):
    headers = {"Authorization": f"Bearer {token}"}
    params = {"patient_id": patient_id}
    body = {}
    if status:
        body["status"] = status
    if note:
        body["note"] = note
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://localhost:8000/api/v1/alerts/alerts/{alert_id}/acknowledge",
            headers=headers,
            params=params,
            json=body,
        )
        response.raise_for_status()
        return response.json()
```

---

## Migration Strategy

### Phase 1: Dual Support (Current)
- Both WebSocket and SSE endpoints are available
- Existing WebSocket clients continue to work
- New clients should use SSE

### Phase 2: Gradual Migration
1. Update frontend applications to use SSE
2. Monitor SSE adoption metrics
3. Provide migration guides to API consumers
4. Set deprecation timeline for WebSocket alerts

### Phase 3: WebSocket Deprecation
1. Announce deprecation date (e.g., 6 months notice)
2. Add deprecation warnings to WebSocket endpoint
3. Monitor remaining WebSocket usage
4. Remove WebSocket alert endpoint after grace period

---

## Role-Based Access Control

### Supported Roles

| Role | Can Monitor | Scope |
|------|-------------|-------|
| `patient` | Own alerts only | Automatic (uses user's ID) |
| `caregiver` | Assigned patients | Requires `patient_id` |
| `doctor` | Assigned patients | Requires `patient_id` |
| `nurse` | Assigned patients | Requires `patient_id` |
| `dispatcher` | Assigned patients | Requires `patient_id` |
| `first_responder` | Assigned patients | Requires `patient_id` |
| `admin` | All patients | Can use `*` or specific `patient_id` |
| `hospital` | Assigned patients | Requires `patient_id` |

### Permission Validation

The system validates:
1. **Authentication**: Valid JWT token required
2. **Role Membership**: User must have the requested role
3. **Scope Access**: 
   - Patients can only access their own alerts
   - Non-admin roles must specify a patient ID
   - Only admins can use `*` to monitor all patients

---

## Technical Implementation Details

### AlertConnectionManager

The `AlertConnectionManager` now supports both transport mechanisms:

```python
class AlertConnectionManager:
    def __init__(self):
        # WebSocket connections (legacy)
        self._connections: dict[str, dict[str, list[WebSocket]]] = {}
        
        # SSE connections (new): queue-based message delivery
        self._sse_queues: dict[str, dict[str, list[asyncio.Queue]]] = {}
    
    async def send_to_roles(self, patient_id: str, roles: list[str], payload: dict):
        """Broadcasts to both WebSocket and SSE clients."""
        # Send to WebSocket clients
        for role in roles:
            for socket in self._iter_sockets(patient_id, role):
                await socket.send_text(json.dumps(payload))
        
        # Send to SSE clients (queue-based)
        for role in roles:
            for queue in self._iter_sse_queues(patient_id, role):
                queue.put_nowait(payload)
```

### Queue Management

- Each SSE client gets an `asyncio.Queue` with max size of 100
- If queue is full (client too slow), messages are dropped
- Clients are automatically cleaned up on disconnect
- Keepalive messages prevent proxy timeouts

### Error Handling

- **SSE**: Automatic reconnection via `EventSource`
- **WebSocket**: Manual reconnection required
- Both: Proper cleanup on disconnect
- Logging for debugging connection issues

---

## Performance Considerations

### SSE Benefits
- Lower memory per connection (no bidirectional buffer)
- Better HTTP/2 multiplexing
- Simpler server implementation
- Browser-native reconnection logic

### SSE Limitations
- Text-only (JSON serialization required)
- Higher overhead per message vs WebSocket
- Not suitable for high-frequency data (use WebSocket for vitals)

### Recommended Limits
- Max 100 pending messages per SSE client
- 30-second keepalive interval
- Automatic cleanup of slow clients

---

## Monitoring and Debugging

### Logs

SSE connections log the following events:
```
sse alert stream connected (role, patient_id, user_id)
sse client disconnected (role, patient_id)
sse stream error (error, role, patient_id)
sse alert stream closed (role, patient_id)
```

### Metrics to Track
- Number of active SSE connections
- Number of active WebSocket connections
- Alert delivery latency
- Queue overflow events
- Reconnection frequency

---

## Testing

### Unit Tests
See `tests/modules/alerts/test_sse_router.py` for comprehensive test coverage:
- SSE stream authentication
- Role-based access control
- Alert delivery
- HTTP acknowledgment
- Error handling

### Integration Testing
```bash
# Run alert tests
pytest tests/modules/alerts/test_sse_router.py -v

# Run all alert-related tests
pytest tests/modules/alerts/ -v
```

### Manual Testing
```bash
# Test SSE stream with curl
curl -N -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/api/v1/alerts/stream?role=caregiver&patient_id=123"

# Test acknowledgment
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"resolved"}' \
  "http://localhost:8000/api/v1/alerts/alerts/ALERT_ID/acknowledge?patient_id=123"
```

---

## FAQ

**Q: Should I migrate from WebSocket to SSE for alerts?**  
A: Yes, SSE is the recommended approach for new implementations. It provides better reliability and simpler client code.

**Q: Will WebSocket alerts be removed?**  
A: Not immediately. We'll maintain backward compatibility for at least 6 months before deprecating.

**Q: Can I use SSE for vitals streaming?**  
A: No, vitals should continue using WebSocket due to high-frequency requirements and bidirectional communication.

**Q: How do I handle reconnections with SSE?**  
A: The browser's `EventSource` API handles reconnections automatically. No additional code needed.

**Q: What happens if my SSE client is too slow?**  
A: Messages will be dropped if the queue fills up (100 messages). Ensure your client processes alerts promptly.

**Q: Can I use SSE with mobile apps?**  
A: Yes, but you'll need an SSE client library. For native apps, consider using WebSocket or HTTP polling instead.

---

## Summary

| Feature | WebSocket (Alerts) | SSE (Alerts) | WebSocket (Vitals) |
|---------|-------------------|--------------|-------------------|
| **Direction** | Bidirectional | Unidirectional | Bidirectional |
| **Reconnection** | Manual | Automatic | Manual |
| **Use Case** | Legacy support | Alert notifications | Real-time vitals |
| **Status** | Deprecated (alerts) | Recommended | Recommended |
| **Frequency** | Low | Low | High (100-500 Hz) |
| **Overhead** | Medium | Higher | Low |

**Recommendation**: Use SSE for alert notifications and WebSocket for vitals streaming.
