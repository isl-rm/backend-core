# Alerts Workflow (Mock AI)

This doc explains how vitals and alerts flow through the system, which WebSocket to use, and who should subscribe.

## Architecture overview

- **Vitals pipeline** receives live measurements, persists them, and broadcasts raw data.
- **Decision engine (mock AI)** evaluates vitals and outputs alert decisions (tier, thresholds, window).
- **Alert service** routes decisions, handles escalation, and manages acknowledgments.
- **Alerts WebSocket** is the dedicated channel for alert delivery and patient acknowledgments.

There is no duplication of work. Vitals are processed once, and alerts are emitted only when thresholds are met.

## Data flow (end-to-end)

1. **Mobile device -> Vitals WS**  
   `ws://<host>/api/v1/vitals/ws/mobile?token=<jwt>`  
   The mobile client streams vitals to the backend.

2. **Server persists + forwards raw vitals**  
   `VitalService.process_vital_stream` stores the vital and broadcasts raw data to frontend consumers at:  
   `ws://<host>/api/v1/vitals/ws/frontend`

3. **Decision engine evaluates the vital**  
   `VitalService.process_vital_stream` calls `AlertService.process_vital`, which delegates to the decision engine to:
   - check the last N samples,
   - select the highest severity level that matches,
   - return a decision.

4. **Alert service routes the decision**  
   The alert service emits an `alert` event to the Alerts WS and schedules escalation if needed.

5. **Alert delivery + escalation**  
   Alerts are sent to subscribers of the Alerts WS. If the patient does not ACK within the configured time (default 30s), the system sends an `alert_escalated` event to the escalation recipients.

## WebSockets and who should subscribe

### Vitals WebSocket

- **Mobile producer**  
  `ws://<host>/api/v1/vitals/ws/mobile?token=<jwt>`  
  Sends live vitals to the backend.

- **Frontend consumer**  
  `ws://<host>/api/v1/vitals/ws/frontend`  
  Receives raw vitals for real-time charts and dashboards.

This channel is **not** used for alerts.

### Alerts WebSocket

`ws://<host>/api/v1/alerts/ws?role=<role>&token=<jwt>[&patient_id=<id>]`

- **Patient** (self-scoped; `patient_id` ignored)  
  `role=patient`

- **Caregiver / Dispatcher / Doctor / Nurse / First Responder**  
  Must have matching roles and provide a concrete `patient_id`.

- **Admin**  
  Can subscribe to all patients using `patient_id=*`.

This channel receives `alert`, `alert_escalated`, and `alert_acknowledged` events and accepts patient ACKs.

## ACK flow

Patients acknowledge alerts on the Alerts WS. The optional `status` field can be used
to mark alerts as confirmed or false alarms.

```json
{
  "event": "ack",
  "alertId": "<id>",
  "patientId": "<patient_id>",
  "status": "confirmed",
  "note": "Patient feeling fine, no symptoms"
}
```

The ACK cancels the escalation timer and broadcasts `alert_acknowledged` to all recipients for that alert.

## Configuration

Rules live in:

- `app/modules/alerts/mock_rules.json`

Key knobs:

- `levels`: severity tiers (`slight`, `moderate`, `critical`, etc.)
- `consecutiveSamples`: how many recent samples must be outside bounds
- `escalateAfterSeconds`: how long to wait before escalation
- `initialRecipients` and `escalationRecipients`: routing targets by tier
- `vitals.<type>.levels`: per-tier min/max thresholds

## Example alert payload

```json
{
  "event": "alert",
  "alertId": "dda6f61b8eb64fd9b9d726be638d94bf",
  "tier": "critical",
  "patientId": "6939f09ecfbe708c1ce1d5b6",
  "vitalType": "heart_rate",
  "vitalsWindow": [190, 192, 188],
  "threshold": { "min": 40, "max": 180 },
  "reasons": ["heart_rate outside 40-180 for 3 samples"],
  "recipients": ["patient"],
  "timestamp": "2025-12-22T18:22:27Z",
  "context": null,
  "source": "mock_ai"
}
```

## Code touchpoints

- Vitals ingestion: `app/modules/vitals/router/ws_mobile.py`
- Vitals processing: `app/modules/vitals/service.py` (`process_vital_stream`)
- Decision engine: `app/modules/alerts/decision.py`
- Alert service: `app/modules/alerts/engine.py`
- Alerts WS: `app/modules/alerts/router.py`
