"""
Example SSE client for alert notifications.

This script demonstrates how to connect to the SSE alert stream
and handle incoming alerts.

Usage:
    python examples/sse_alert_client.py --token YOUR_JWT_TOKEN --role caregiver --patient-id 123
"""

import argparse
import asyncio
import json
import sys
from typing import Any

import httpx


class AlertSSEClient:
    """Client for consuming alert notifications via SSE."""

    def __init__(self, base_url: str, token: str, role: str, patient_id: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.role = role
        self.patient_id = patient_id
        self.running = False

    async def connect(self) -> None:
        """Connect to the SSE stream and process alerts."""
        headers = {"Authorization": f"Bearer {self.token}"}
        params = {"role": self.role}
        if self.patient_id:
            params["patient_id"] = self.patient_id

        url = f"{self.base_url}/api/v1/alerts/stream"
        print(f"Connecting to {url}...")
        print(f"Role: {self.role}, Patient ID: {self.patient_id or 'N/A'}")
        print("-" * 60)

        self.running = True

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "GET",
                    url,
                    headers=headers,
                    params=params,
                ) as response:
                    if response.status_code != 200:
                        print(f"Error: {response.status_code}")
                        print(await response.aread())
                        return

                    print("✓ Connected to alert stream")
                    print("Waiting for alerts...\n")

                    async for line in response.aiter_lines():
                        if not self.running:
                            break

                        if line.startswith("data:"):
                            # Parse JSON data
                            data_str = line[5:].strip()
                            try:
                                alert = json.loads(data_str)
                                await self.handle_alert(alert)
                            except json.JSONDecodeError as e:
                                print(f"Error parsing alert: {e}")

                        elif line.startswith(":"):
                            # Keepalive comment
                            print(".", end="", flush=True)

        except httpx.HTTPError as e:
            print(f"\nConnection error: {e}")
        except KeyboardInterrupt:
            print("\n\nDisconnecting...")
        finally:
            self.running = False
            print("Disconnected from alert stream")

    async def handle_alert(self, alert: dict[str, Any]) -> None:
        """Process an incoming alert."""
        event = alert.get("event", "unknown")

        print("\n" + "=" * 60)

        if event == "alert":
            self._print_new_alert(alert)
        elif event == "alert_escalated":
            self._print_escalated_alert(alert)
        elif event == "alert_acknowledged":
            self._print_acknowledged_alert(alert)
        else:
            print(f"Unknown event: {event}")
            print(json.dumps(alert, indent=2))

        print("=" * 60 + "\n")

    def _print_new_alert(self, alert: dict[str, Any]) -> None:
        """Print a new alert notification."""
        print("🚨 NEW ALERT")
        print(f"Alert ID: {alert.get('alertId')}")
        print(f"Tier: {alert.get('tier')}")
        print(f"Patient ID: {alert.get('patientId')}")
        print(f"Vital Type: {alert.get('vitalType')}")
        print(f"Vitals Window: {alert.get('vitalsWindow')}")
        print(f"Threshold: {alert.get('threshold')}")
        print(f"Reasons:")
        for reason in alert.get("reasons", []):
            print(f"  - {reason}")
        print(f"Recipients: {', '.join(alert.get('recipients', []))}")
        print(f"Timestamp: {alert.get('timestamp')}")

    def _print_escalated_alert(self, alert: dict[str, Any]) -> None:
        """Print an escalated alert notification."""
        print("⚠️  ALERT ESCALATED")
        print(f"Alert ID: {alert.get('alertId')}")
        print(f"Tier: {alert.get('tier')}")
        print(f"Patient ID: {alert.get('patientId')}")
        print(f"Vital Type: {alert.get('vitalType')}")
        print(f"New Recipients: {', '.join(alert.get('recipients', []))}")
        print(f"Timestamp: {alert.get('timestamp')}")

    def _print_acknowledged_alert(self, alert: dict[str, Any]) -> None:
        """Print an alert acknowledgment notification."""
        print("✓ ALERT ACKNOWLEDGED")
        print(f"Alert ID: {alert.get('alertId')}")
        print(f"Patient ID: {alert.get('patientId')}")
        print(f"Acknowledged By: {alert.get('acknowledgedBy')}")
        print(f"Status: {alert.get('status', 'N/A')}")
        print(f"Note: {alert.get('note', 'N/A')}")
        print(f"Timestamp: {alert.get('timestamp')}")

    async def acknowledge_alert(
        self,
        alert_id: str,
        patient_id: str,
        status: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Acknowledge an alert via HTTP POST."""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        params = {"patient_id": patient_id}
        body = {}
        if status:
            body["status"] = status
        if note:
            body["note"] = note

        url = f"{self.base_url}/api/v1/alerts/alerts/{alert_id}/acknowledge"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                params=params,
                json=body,
            )
            response.raise_for_status()
            return response.json()


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="SSE Alert Client Example")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--token",
        required=True,
        help="JWT authentication token",
    )
    parser.add_argument(
        "--role",
        required=True,
        choices=["patient", "caregiver", "doctor", "nurse", "dispatcher", "admin"],
        help="User role",
    )
    parser.add_argument(
        "--patient-id",
        help="Patient ID to monitor (required for non-admin roles)",
    )

    args = parser.parse_args()

    # Validate patient_id requirement
    if args.role != "admin" and args.role != "patient" and not args.patient_id:
        print(f"Error: --patient-id is required for role '{args.role}'")
        sys.exit(1)

    client = AlertSSEClient(
        base_url=args.base_url,
        token=args.token,
        role=args.role,
        patient_id=args.patient_id,
    )

    await client.connect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
