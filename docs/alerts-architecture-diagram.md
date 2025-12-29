# Alert Notification Architecture

## Current Hybrid Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ALERT NOTIFICATIONS                          │
│                     (Dual Transport Support)                         │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                          ALERT SOURCES                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Vital Signs Monitor → AlertDecisionEngine → AlertService           │
│  (Heart Rate, BP, etc.)                                             │
│                                                                      │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   AlertConnectionManager                             │
│                   (Dual Transport Broker)                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────┐         ┌──────────────────────┐          │
│  │  WebSocket Clients  │         │    SSE Clients       │          │
│  │    (Legacy)         │         │  (Recommended)       │          │
│  │                     │         │                      │          │
│  │  _connections:      │         │  _sse_queues:        │          │
│  │  {patient_id: {     │         │  {patient_id: {      │          │
│  │    role: [sockets]  │         │    role: [queues]    │          │
│  │  }}                 │         │  }}                  │          │
│  └─────────────────────┘         └──────────────────────┘          │
│                                                                      │
│  send_to_roles() → Broadcasts to BOTH transports                    │
│                                                                      │
└──────────────┬────────────────────────────────┬─────────────────────┘
               │                                │
               ▼                                ▼
┌──────────────────────────┐    ┌──────────────────────────────────┐
│   WebSocket Endpoint     │    │      SSE Endpoint                │
│   /api/v1/alerts/ws      │    │   /api/v1/alerts/stream          │
├──────────────────────────┤    ├──────────────────────────────────┤
│                          │    │                                  │
│ • Bidirectional          │    │ • Unidirectional (server→client) │
│ • Manual reconnection    │    │ • Auto-reconnection (EventSource)│
│ • Legacy support         │    │ • HTTP/2 multiplexing            │
│ • Ack via WebSocket msg  │    │ • Better proxy compatibility     │
│                          │    │ • Ack via HTTP POST              │
│                          │    │                                  │
└──────────────┬───────────┘    └──────────────┬───────────────────┘
               │                               │
               ▼                               ▼
┌──────────────────────────┐    ┌──────────────────────────────────┐
│   Legacy Clients         │    │      Modern Clients              │
│   (WebSocket)            │    │      (SSE + HTTP)                │
├──────────────────────────┤    ├──────────────────────────────────┤
│                          │    │                                  │
│ const ws = new           │    │ const eventSource = new          │
│   WebSocket(url);        │    │   EventSource(url);              │
│                          │    │                                  │
│ ws.onmessage = (msg) => {│    │ eventSource.onmessage = (e) => { │
│   handleAlert(msg);      │    │   handleAlert(e.data);           │
│ };                       │    │ };                               │
│                          │    │                                  │
│ // Acknowledge via WS    │    │ // Acknowledge via HTTP POST     │
│ ws.send(JSON.stringify({ │    │ await fetch(                     │
│   event: 'ack',          │    │   `/alerts/${id}/acknowledge`,   │
│   alertId: id            │    │   { method: 'POST', ... }        │
│ }));                     │    │ );                               │
│                          │    │                                  │
└──────────────────────────┘    └──────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────┐
│                    VITALS STREAMING                                  │
│                   (WebSocket Only - Optimized)                       │
└─────────────────────────────────────────────────────────────────────┘

Mobile App ──WS──> VitalConnectionManager ──WS──> Frontend Dashboard
   (Producer)      (High-frequency ECG data)        (Consumer)
   
   • 100-500 Hz sample rate
   • Bidirectional communication
   • Low latency requirement
   • Binary frame support
```

## Message Flow Examples

### SSE Alert Flow

```
1. Vital Signs Monitor detects anomaly
   └─> AlertDecisionEngine evaluates rules
       └─> AlertService.process_vital()
           └─> AlertConnectionManager.send_to_roles()
               ├─> WebSocket clients (legacy)
               │   └─> ws.send_text(json_payload)
               │
               └─> SSE clients (new)
                   └─> queue.put_nowait(payload)
                       └─> event_generator yields "data: {json}\n\n"
                           └─> EventSource.onmessage fires
                               └─> Client handles alert

2. User acknowledges alert
   └─> HTTP POST /alerts/{id}/acknowledge
       └─> AlertService.acknowledge()
           └─> AlertConnectionManager.send_to_roles()
               └─> Broadcasts acknowledgment to all subscribers
```

### Role-Based Routing

```
Alert Tier: CRITICAL
Initial Recipients: ["caregiver"]
Escalation Recipients: ["doctor", "nurse"]

AlertConnectionManager.send_to_roles(patient_id="123", roles=["caregiver"])
├─> Finds all WebSocket connections for:
│   ├─> patient_id="123", role="caregiver"
│   └─> patient_id="*", role="caregiver" (admin monitoring all)
│
└─> Finds all SSE queues for:
    ├─> patient_id="123", role="caregiver"
    └─> patient_id="*", role="caregiver" (admin monitoring all)

If not acknowledged within escalate_after_seconds:
└─> AlertConnectionManager.send_to_roles(patient_id="123", roles=["doctor", "nurse"])
    └─> Escalated alert sent to doctor and nurse subscribers
```

## Comparison Matrix

| Feature                  | WebSocket (Alerts) | SSE (Alerts)     | WebSocket (Vitals) |
|--------------------------|-------------------|------------------|-------------------|
| **Direction**            | Bidirectional     | Unidirectional   | Bidirectional     |
| **Reconnection**         | Manual            | Automatic        | Manual            |
| **Browser API**          | WebSocket         | EventSource      | WebSocket         |
| **Proxy Friendly**       | Moderate          | Excellent        | Moderate          |
| **HTTP/2 Multiplexing**  | No                | Yes              | No                |
| **Message Overhead**     | Low               | Medium           | Very Low          |
| **Use Case**             | Legacy support    | Notifications    | Real-time data    |
| **Frequency**            | Low               | Low              | High (100-500 Hz) |
| **Status**               | Deprecated        | Recommended      | Recommended       |

## Migration Timeline

```
Phase 1: Dual Support (Current)
├─ Both WebSocket and SSE available
├─ Existing clients continue working
└─ New clients use SSE

Phase 2: Gradual Migration (Next 3-6 months)
├─ Update frontend applications
├─ Monitor adoption metrics
├─ Provide migration guides
└─ Set deprecation timeline

Phase 3: WebSocket Deprecation (6+ months)
├─ Announce deprecation date
├─ Add deprecation warnings
├─ Monitor remaining usage
└─ Remove WebSocket alerts endpoint
```
