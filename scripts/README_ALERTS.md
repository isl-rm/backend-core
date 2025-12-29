# Alert System Testing Scripts

This directory contains scripts to test the SSE (Server-Sent Events) alert system.

## Quick Start

### Option 1: Interactive Bash Script (Easiest)

```bash
./scripts/test_alerts.sh
```

This will show you a menu with options to:
1. Listen to alerts (SSE stream)
2. Send test vitals (may trigger alerts)
3. Send manual alerts
4. Test connection

### Option 2: Python Script for Listening

Install dependencies first:
```bash
pip install httpx typer
```

Then listen to alerts:
```bash
python scripts/test_alert_sender.py listen --role caregiver --patient-id YOUR_PATIENT_ID
```

### Option 3: Send Manual Alerts

```bash
python scripts/send_test_alert.py
```

This will prompt you for:
- Patient ID
- Roles (who should receive the alert)
- Vital type
- Alert tier (CRITICAL, WARNING, INFO)

### Option 4: Simple curl Command

```bash
# Get token first
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}' \
  | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

# Listen to alerts
curl -N -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/alerts/stream?role=caregiver&patient_id=YOUR_PATIENT_ID"
```

## Testing Workflow

### 1. Start Listening (Terminal 1)

```bash
./scripts/test_alerts.sh
# Choose option 1 (Listen to alerts)
# Enter role: caregiver
# Enter patient ID: test-patient-123
```

### 2. Send an Alert (Terminal 2)

```bash
python scripts/send_test_alert.py
# Follow the prompts
```

You should see the alert appear in Terminal 1!

## Understanding SSE Behavior

When you connect to the SSE endpoint:

1. **Initial Connection**: You'll see HTTP 200 and headers confirming the connection
2. **Keepalive Messages**: Every 30 seconds, you'll see `: keepalive` (these are comments)
3. **Alert Events**: When an alert is triggered, you'll see `data: {json_alert_data}`

**Important**: The connection stays open indefinitely. This is normal SSE behavior!

## Scripts Overview

### `test_alerts.sh`
Interactive bash script with menu-driven interface. Best for quick testing.

### `test_alert_sender.py`
Full-featured Python CLI tool with commands:
- `listen`: Connect to SSE stream and display alerts
- `send-vital`: Send a vital reading (may trigger alert based on thresholds)
- `test-connection`: Verify API connectivity

### `send_test_alert.py`
Simple Python script to manually broadcast alerts through the alert manager.
Useful for testing without needing to trigger threshold violations.

## Troubleshooting

### "Loading" in Swagger UI
This is **normal**! SSE streams stay open indefinitely. Use curl or the provided scripts instead.

### No Alerts Received
1. Make sure you're listening **before** sending the alert
2. Verify the patient_id matches
3. Verify the role matches the alert recipients
4. Check that the server is running: `curl http://localhost:8000/health`

### Authentication Errors
1. Make sure you have a user account created
2. Update the email/password in the scripts if needed
3. Check that the auth service is working: `curl -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"email":"test@example.com","password":"password123"}'`

## Examples

### Listen as Admin (All Patients)
```bash
python scripts/test_alert_sender.py listen --role admin --patient-id "*"
```

### Send High Heart Rate
```bash
python scripts/test_alert_sender.py send-vital --patient-id test-123 --vital-type heart_rate --value 180
```

### Custom Alert
```bash
python scripts/send_test_alert.py
# Patient ID: patient-456
# Roles: doctor,nurse
# Vital Type: blood_pressure
# Tier: WARNING
```

## Integration with Frontend

To integrate with a web frontend, use the EventSource API:

```javascript
const eventSource = new EventSource(
  `http://localhost:8000/api/v1/alerts/stream?role=caregiver&patient_id=${patientId}`,
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);

eventSource.onmessage = (event) => {
  const alert = JSON.parse(event.data);
  console.log('Alert received:', alert);
  // Handle alert in your UI
};

eventSource.onerror = (error) => {
  console.error('SSE error:', error);
};
```

## Notes

- SSE connections are one-way (server → client)
- To acknowledge alerts, use the HTTP POST endpoint: `/api/v1/alerts/alerts/{alert_id}/acknowledge`
- The system supports both SSE and WebSocket connections simultaneously
- Alerts are broadcast to all connected clients matching the role and patient criteria
