# API Endpoints Documentation

This document provides a comprehensive reference for all available API endpoints in the Backend Core API.

**Base URL:** `/api/v1`

**Authentication:** Most endpoints require Bearer token authentication. Include the token in the `Authorization` header:
```
Authorization: Bearer <your_access_token>
```

---

## Table of Contents

- [Authentication](#authentication)
- [Users](#users)
- [Vitals](#vitals)
- [Alerts](#alerts)
- [Daily Check-in](#daily-check-in)
- [Caregivers](#caregivers)
  - [Patient Management](#patient-management)
  - [Access Requests](#access-requests)
  - [Vitals Monitoring](#vitals-monitoring)
  - [Alerts Streaming](#alerts-streaming)
  - [Conditions Monitoring](#conditions-monitoring)
  - [Messages](#messages)
- [Patients](#patients)
- [Chat](#chat)
- [Health Check](#health-check)

---

## Authentication

### POST `/api/v1/login/access-token`

**Summary:** Login to get access token

**Description:** OAuth2 compatible token login. Designed for mobile clients, third-party applications, or clients that prefer to handle the access token manually in the Authorization header.

**Request Body:**
- `email` (string, required): User email
- `password` (string, required): User password

**Response:** `AccessTokenWithUserResponse`
- `access_token` (string): JWT access token (short-lived)
- `token_type` (string): Always "bearer"
- `user` (UserResponse): Full user profile and preferences

**Side Effect:** Sets a `refresh_token` HTTP-only cookie for simplified token rotation.

**Status Code:** 200 OK

---

### POST `/api/v1/login/cookie`

**Summary:** Login to set auth cookies

**Description:** Login using email/password and set access + refresh cookies for web clients. Designed for first-party web frontend (SPA). Moves token storage to secure, HTTP-only cookies.

**Request Body:**
- `email` (string, required): User email
- `password` (string, required): User password

**Response:** `UserResponse`
- Full user profile and preferences

**Side Effect:** 
- Sets `access_token` HTTP-only cookie
- Sets `refresh_token` HTTP-only cookie

**Status Code:** 200 OK

---

### POST `/api/v1/refresh-token`

**Summary:** Refresh access token

**Description:** Get a new access token using a refresh token.

**Request Body (Optional):**
- `refresh_token` (string): Refresh token (can also be provided via cookie)

**Cookie:**
- `refresh_token`: Refresh token cookie

**Response:** `AccessTokenResponse`
- `access_token` (string): New JWT access token
- `token_type` (string): Always "bearer"

**Side Effect:** Sets new access and refresh token cookies

**Status Code:** 200 OK

---

### POST `/api/v1/logout`

**Summary:** Logout and clear auth cookies

**Description:** Clear auth cookies. If refresh tokens are stored server-side, revoke them here as well.

**Response:** No content

**Status Code:** 204 No Content

---

### POST `/api/v1/signup`

**Summary:** Register a new user

**Description:** Create a new user account without authentication.

**Request Body:** `UserCreate`
- `email` (string, required): User email
- `password` (string, required): User password
- `full_name` (string, optional): User's full name
- Additional user fields as defined in schema

**Response:** `UserResponse`
- Created user details

**Status Code:** 201 Created

---

## Users

### GET `/api/v1/users/me`

**Summary:** Get current user info

**Description:** Get the currently authenticated user's information.

**Authentication:** Required (Bearer token)

**Response:** `UserResponse`
- Current user details including profile and preferences

**Status Code:** 200 OK

---

## Vitals

### POST `/api/v1/vitals/`

**Summary:** Record a new vital sign

**Description:** Record a new vital sign measurement for the authenticated user.

**Authentication:** Required (Bearer token)

**Request Body:** `VitalCreate`
- `type` (VitalType, required): Type of vital (ECG, BPM, GYROSCOPE, HEART_RATE)
- `value` (float, required): Vital measurement value
- `unit` (string, optional): Unit of measurement
- `timestamp` (datetime, optional): Timestamp of measurement

**Response:** `Vital`
- Created vital record

**Status Code:** 201 Created

---

### POST `/api/v1/vitals/bulk`

**Summary:** Record multiple vital signs

**Description:** Record multiple vital sign measurements for the authenticated user in one request.

**Authentication:** Required (Bearer token)

**Request Body:** `VitalBulkCreate`
- `vitals` (array of VitalCreate): List of vital measurements

**Response:** Array of `Vital`
- Created vital records

**Status Code:** 201 Created

---

### GET `/api/v1/vitals/history`

**Summary:** Get vital signs history

**Description:** Get a user's vital history with optional type filter and pagination. Defaults to last 24 hours.

**Authentication:** Required (Bearer token)

**Query Parameters:**
- `type` (VitalType, optional): Filter by vital type
- `limit` (integer, optional): Maximum number of results
- `skip` (integer, optional): Number of results to skip
- `start` (datetime, optional): Start date/time
- `end` (datetime, optional): End date/time

**Response:** Array of `Vital`
- Vital history records

**Status Code:** 200 OK

---

### GET `/api/v1/vitals/series`

**Summary:** Get vitals time series (raw or daily average)

**Description:** Return raw data when the range is ≤3 days; otherwise return daily averages. Defaults to the last 24 hours and supports pagination.

**Authentication:** Required (Bearer token)

**Query Parameters:**
- `type` (VitalType, required): Vital type to retrieve
- `start` (datetime, optional): Start date/time
- `end` (datetime, optional): End date/time
- `limit` (integer, optional): Maximum number of results
- `skip` (integer, optional): Number of results to skip

**Response:** `VitalSeriesResponse`
- Time series data (raw or aggregated)

**Status Code:** 200 OK

---

### GET `/api/v1/vitals/latest`

**Summary:** Get most recent vital sign

**Description:** Fetch the newest vital for the authenticated user, optionally by type.

**Authentication:** Required (Bearer token)

**Query Parameters:**
- `type` (VitalType, optional): Filter by vital type

**Response:** `Vital`
- Latest vital record

**Status Code:** 200 OK

---

### GET `/api/v1/vitals/dashboard`

**Summary:** Get vitals dashboard summary

**Description:** Return the latest vitals mapped to the dashboard contract.

**Authentication:** Required (Bearer token)

**Response:** `DashboardSummary`
- Dashboard summary with latest vitals

**Status Code:** 200 OK

---

### WebSocket `/api/v1/vitals/ws/mobile`

**Summary:** WebSocket endpoint for mobile app (producer)

**Description:** Auth via `token` query param, then stream inbound vitals to persistence + broadcast.

**Query Parameters:**
- `token` (string, required): JWT authentication token

**Message Format:**
- ECG: `{"type": "ECG", "sampleRate": number, "samples": array, "bpm": number, "timestamp": string}`
- Other vitals: `{"type": string, "value": number, "unit": string, "timestamp": string}`

**Authentication:** Required (via token query param)

---

### WebSocket `/api/v1/vitals/ws/frontend`

**Summary:** WebSocket endpoint for frontend (consumer)

**Description:** Receives broadcasted vital data from mobile devices.

**Authentication:** Not required

**Message Format:** Receives vital data broadcasts

---

## Alerts

### WebSocket `/api/v1/alerts/ws`

**Summary:** WebSocket endpoint for alert notifications (legacy)

**Description:** Kept for backward compatibility during SSE migration.

**Query Parameters:**
- `token` (string, required): JWT authentication token
- `role` (string, required): User role (caregiver, doctor, nurse, dispatcher, admin, patient, etc.)
- `patient_id` (string, optional): Patient ID to monitor (required for non-admin roles)

**Message Format (Acknowledgment):**
```json
{
  "event": "ack",
  "alertId": "string",
  "patientId": "string",
  "status": "string",
  "note": "string"
}
```

**Authentication:** Required (via token query param)

---

### GET `/api/v1/alerts/stream`

**Summary:** Server-Sent Events (SSE) endpoint for real-time alert notifications

**Description:** SSE endpoint for real-time alert notifications. Auto-reconnects on disconnect.

**Authentication:** Required (Bearer token)

**Query Parameters:**
- `role` (string, required): User role (caregiver, doctor, nurse, dispatcher, admin, etc.)
- `patient_id` (string, optional): Patient ID to monitor (optional for admin, required for others)

**Response:** SSE stream
- Event format: `data: {alert_data}\n\n`
- Keepalive: `: keepalive\n\n` (sent every 30 seconds)

**Status Code:** 200 OK

---

### POST `/api/v1/alerts/alerts/{alert_id}/acknowledge`

**Summary:** Acknowledge an alert via HTTP POST (for SSE clients)

**Authentication:** Required (Bearer token)

**Path Parameters:**
- `alert_id` (string, required): The alert ID to acknowledge

**Query Parameters:**
- `patient_id` (string, required): The patient ID associated with the alert

**Request Body:** `AlertAcknowledgmentRequest`
- `status` (string, optional): Acknowledgment status
- `note` (string, optional): Note from the acknowledging user

**Response:**
```json
{
  "message": "Alert acknowledged successfully",
  "alert_id": "string"
}
```

**Status Code:** 200 OK

---

## Daily Check-in

### GET `/api/v1/daily-checkin/today`

**Summary:** Get today's check-in

**Description:** Retrieve the daily check-in for the current day.

**Authentication:** Required (Bearer token)

**Response:** `DailyCheckinResponse`
- Today's check-in data

**Status Code:** 200 OK

---

### PUT `/api/v1/daily-checkin/today`

**Summary:** Save today's check-in

**Description:** Create or update today's daily check-in.

**Authentication:** Required (Bearer token)

**Request Body:** `DailyCheckinUpdate`
- Check-in data fields

**Response:** `DailyCheckinResponse`
- Updated check-in data

**Status Code:** 200 OK

---

### PATCH `/api/v1/daily-checkin/today/kicks`

**Summary:** Increment kick counter

**Description:** Increment the kick counter for today's check-in.

**Authentication:** Required (Bearer token)

**Request Body:** `IncrementRequest`
- `delta` (integer, required): Amount to increment (can be negative)

**Response:** `DailyCheckinResponse`
- Updated check-in data

**Status Code:** 200 OK

---

### PATCH `/api/v1/daily-checkin/today/hydration`

**Summary:** Increment hydration counter

**Description:** Increment the hydration counter for today's check-in.

**Authentication:** Required (Bearer token)

**Request Body:** `IncrementRequest`
- `delta` (integer, required): Amount to increment (can be negative)

**Response:** `DailyCheckinResponse`
- Updated check-in data

**Status Code:** 200 OK

---

### PATCH `/api/v1/daily-checkin/today/plan/{item_id}`

**Summary:** Update a plan item

**Description:** Update a specific plan item in today's check-in.

**Authentication:** Required (Bearer token)

**Path Parameters:**
- `item_id` (string, required): Plan item ID

**Request Body:** `PlanItemUpdateRequest`
- Plan item update fields

**Response:** `DailyCheckinResponse`
- Updated check-in data

**Status Code:** 200 OK

---

### POST `/api/v1/daily-checkin/today/plan`

**Summary:** Add a plan item

**Description:** Add a new plan item to today's check-in.

**Authentication:** Required (Bearer token)

**Request Body:** `PlanItemCreateRequest`
- Plan item data

**Response:** `DailyCheckinResponse`
- Updated check-in data

**Status Code:** 200 OK

---

### PATCH `/api/v1/daily-checkin/today/substance`

**Summary:** Update substance use status for today

**Description:** Update substance use information for today's check-in.

**Authentication:** Required (Bearer token)

**Request Body:** `SubstanceUse`
- Substance use data

**Response:** `DailyCheckinResponse`
- Updated check-in data

**Status Code:** 200 OK

---

### GET `/api/v1/daily-checkin/history`

**Summary:** List daily check-in history

**Description:** Retrieve historical daily check-in records.

**Authentication:** Required (Bearer token)

**Query Parameters:**
- Pagination and filter parameters (as defined in `HistoryQuery`)

**Response:** `HistoryResponse`
- Historical check-in records

**Status Code:** 200 OK

---

### GET `/api/v1/daily-checkin/history/range`

**Summary:** List daily check-ins by date range

**Description:** Retrieve daily check-ins within a specific date range.

**Authentication:** Required (Bearer token)

**Query Parameters:**
- Date range parameters (as defined in `HistoryRangeQuery`)

**Response:** `DailyCheckinHistoryResponse`
- Check-in records within the specified range

**Status Code:** 200 OK

---

### PUT `/api/v1/daily-checkin/history/{id}`

**Summary:** Update a specific check-in

**Description:** Update a historical daily check-in record.

**Authentication:** Required (Bearer token)

**Path Parameters:**
- `id` (string, required): Check-in record ID

**Request Body:** `DailyCheckinUpdate`
- Updated check-in data

**Response:** `DailyCheckinResponse`
- Updated check-in record

**Status Code:** 200 OK

---

## Caregivers

### Patient Management

#### GET `/api/v1/caregivers/patients`

**Summary:** List patients for caregiver

**Description:** Get all patients assigned to the authenticated caregiver.

**Authentication:** Required (Bearer token, CAREGIVER role)

**Response:** Array of `UserResponse`
- List of patient profiles

**Status Code:** 200 OK

---

#### GET `/api/v1/caregivers/patients/moderate`

**Summary:** List moderate-condition patients for caregiver

**Description:** Get patients with moderate condition severity assigned to the authenticated caregiver.

**Authentication:** Required (Bearer token, CAREGIVER role)

**Response:** Array of `UserResponse`
- List of moderate-condition patient profiles

**Status Code:** 200 OK

---

#### GET `/api/v1/caregivers/patients/critical`

**Summary:** List critical-condition patients for caregiver

**Description:** Get patients with critical condition severity assigned to the authenticated caregiver.

**Authentication:** Required (Bearer token, CAREGIVER role)

**Response:** Array of `UserResponse`
- List of critical-condition patient profiles

**Status Code:** 200 OK

---

#### POST `/api/v1/caregivers/access`

**Summary:** Grant caregiver access to a patient

**Description:** Admin endpoint to grant a caregiver access to a patient's data.

**Authentication:** Required (Bearer token, ADMIN role)

**Request Body:** `CaregiverPatientAccessRequest`
- `caregiver_id` (string, required): Caregiver user ID
- `patient_id` (string, required): Patient user ID

**Response:** `CaregiverPatientAccessResponse`
- Access mapping details

**Status Code:** 201 Created

---

#### DELETE `/api/v1/caregivers/access`

**Summary:** Revoke caregiver access to a patient

**Description:** Admin endpoint to revoke a caregiver's access to a patient's data.

**Authentication:** Required (Bearer token, ADMIN role)

**Request Body:** `CaregiverPatientAccessRequest`
- `caregiver_id` (string, required): Caregiver user ID
- `patient_id` (string, required): Patient user ID

**Response:** `CaregiverPatientAccessResponse`
- Updated access mapping details

**Status Code:** 200 OK

---

### Access Requests

#### POST `/api/v1/caregivers/access-requests/caregiver`

**Summary:** Caregiver requests access to a patient

**Description:** Caregiver initiates a request to access a patient's data.

**Authentication:** Required (Bearer token, CAREGIVER role - not admin)

**Request Body:** `CaregiverAccessRequestCreateForCaregiver`
- `patient_id` (string, required): Patient user ID

**Response:** `CaregiverAccessRequestResponse`
- Created access request details

**Status Code:** 201 Created

---

#### POST `/api/v1/caregivers/access-requests/patient`

**Summary:** Patient invites a caregiver

**Description:** Patient initiates an invitation for a caregiver to access their data.

**Authentication:** Required (Bearer token, USER role - not admin)

**Request Body:** `CaregiverAccessRequestCreateForPatient`
- `caregiver_id` (string, required): Caregiver user ID

**Response:** `CaregiverAccessRequestResponse`
- Created access request details

**Status Code:** 201 Created

---

#### GET `/api/v1/caregivers/access-requests/incoming`

**Summary:** List incoming patient access requests

**Description:** Get all pending access requests for the authenticated caregiver.

**Authentication:** Required (Bearer token, CAREGIVER role - not admin)

**Response:** Array of `CaregiverAccessRequestResponse`
- List of incoming access requests

**Status Code:** 200 OK

---

#### POST `/api/v1/caregivers/access-requests/{request_id}/accept`

**Summary:** Accept a caregiver/patient access request

**Description:** Accept a pending access request (can be called by either caregiver or patient depending on who initiated).

**Authentication:** Required (Bearer token)

**Path Parameters:**
- `request_id` (string, required): Access request ID

**Response:** `CaregiverAccessRequestResponse`
- Updated access request details

**Status Code:** 200 OK

---

### Vitals Monitoring

#### GET `/api/v1/caregivers/patients/{patient_id}/dashboard`

**Summary:** Get vitals dashboard summary for a patient

**Description:** Return the latest vitals dashboard summary for a specific patient. The caregiver must have active access to the patient.

**Authentication:** Required (Bearer token, CAREGIVER role)

**Path Parameters:**
- `patient_id` (string, required): Patient user ID

**Response:** `DashboardSummary`
- Patient's vitals dashboard summary

**Status Code:** 200 OK

---

#### WebSocket `/api/v1/caregivers/ws/vitals`

**Summary:** WebSocket for patient vital updates

**Description:** Caregiver WebSocket for receiving real-time vital updates from subscribed patients.

**Query Parameters:**
- `token` (string, required): JWT authentication token

**Message Format (Subscribe):**
```json
{
  "event": "start",
  "patientIds": ["patient_id_1", "patient_id_2"]
}
```

**Message Format (Unsubscribe):**
```json
{
  "event": "stop"
}
```

**Authentication:** Required (via token query param, CAREGIVER or ADMIN role)

---

### Alerts Streaming

#### GET `/api/v1/caregivers/alerts/stream`

**Summary:** SSE endpoint for caregivers to receive alerts from all their subscribed patients

**Description:** Automatically subscribes the caregiver to alerts from all patients they have access to. No need to specify individual patient IDs.

**Authentication:** Required (Bearer token, CAREGIVER or ADMIN role)

**Response:** SSE stream
- Event format: `data: {alert_data}\n\n`
- Keepalive: `: keepalive\n\n` (sent every 30 seconds)

**Status Code:** 200 OK

---

### Conditions Monitoring

#### WebSocket `/api/v1/caregivers/ws/conditions`

**Summary:** WebSocket for moderate/critical condition updates

**Description:** Caregiver WebSocket for receiving condition severity updates for subscribed patients.

**Query Parameters:**
- `token` (string, required): JWT authentication token
- `patient_ids` (string, optional): Comma-separated patient IDs
- `severity` (string, optional): Comma-separated severity levels (moderate, critical)

**Authentication:** Required (via token query param, CAREGIVER or ADMIN role)

---

### Messages

#### GET `/api/v1/caregivers/messages`

**Summary:** List caregiver message threads

**Description:** Get all message threads for the authenticated caregiver.

**Authentication:** Required (Bearer token, CAREGIVER role)

**Response:** Array of `MessageThreadPreview`
- List of message threads (currently returns empty array - placeholder)

**Status Code:** 200 OK

---

#### WebSocket `/api/v1/caregivers/ws/messages`

**Summary:** WebSocket for caregiver messaging

**Description:** Placeholder caregiver messaging WebSocket. Broadcasts inbound messages to connected caregivers.

**Query Parameters:**
- `token` (string, required): JWT authentication token

**Authentication:** Required (via token query param, CAREGIVER or ADMIN role)

---

## Patients

### GET `/api/v1/patients/access-requests/incoming`

**Summary:** List incoming caregiver access requests

**Description:** Get all pending caregiver access requests for the authenticated patient.

**Authentication:** Required (Bearer token, USER role - not admin)

**Response:** Array of `CaregiverAccessRequestResponse`
- List of incoming access requests

**Status Code:** 200 OK

---

## Chat

### WebSocket `/api/v1/ws/chat/{client_id}`

**Summary:** WebSocket endpoint for chat

**Description:** Simple chat WebSocket for broadcasting messages.

**Path Parameters:**
- `client_id` (integer, required): Client identifier

**Message Format:** Plain text messages

**Authentication:** Not required

---

## Health Check

### GET `/health`

**Summary:** Health check endpoint

**Description:** Simple health check to verify the API is running.

**Authentication:** Not required

**Response:**
```json
{
  "status": "ok"
}
```

**Status Code:** 200 OK

---

## Common Response Codes

- **200 OK**: Request successful
- **201 Created**: Resource created successfully
- **204 No Content**: Request successful with no response body
- **400 Bad Request**: Invalid request parameters or body
- **401 Unauthorized**: Missing or invalid authentication
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Resource not found
- **500 Internal Server Error**: Server error

---

## WebSocket Connection Codes

- **1000 Normal Closure**: Connection closed normally
- **1008 Policy Violation**: Authentication failed or insufficient permissions

---

## Notes

1. **Authentication**: Most endpoints require a valid JWT Bearer token. Obtain tokens via the `/login/access-token` or `/login/cookie` endpoints.

2. **WebSocket Authentication**: WebSocket endpoints typically use a `token` query parameter for authentication instead of headers.

3. **SSE vs WebSocket**: The API is migrating from WebSocket to Server-Sent Events (SSE) for alert notifications. Both are currently supported for backward compatibility.

4. **Role-Based Access**: Many caregiver endpoints require specific roles (CAREGIVER, ADMIN, etc.). Ensure users have appropriate roles assigned.

5. **Timestamps**: All datetime fields should be in ISO 8601 format with timezone information.

6. **Pagination**: List endpoints support pagination via `limit` and `skip` query parameters.
