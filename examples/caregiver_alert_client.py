#!/usr/bin/env python3
"""
Example client for caregiver alert streaming via SSE.

This script demonstrates how to connect to the caregiver alert stream
and process incoming alerts in real-time.

Usage:
    python examples/caregiver_alert_client.py --token YOUR_JWT_TOKEN
    
    # Or with environment variable
    export CAREGIVER_TOKEN=your_jwt_token
    python examples/caregiver_alert_client.py
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any

import requests


class CaregiverAlertClient:
    """Client for streaming caregiver alerts via SSE."""

    def __init__(self, base_url: str, token: str) -> None:
        """
        Initialize the alert client.

        Args:
            base_url: Base URL of the API (e.g., http://localhost:8000)
            token: JWT authentication token
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}"}

    def stream_alerts(self) -> None:
        """
        Connect to the SSE stream and process alerts.

        This method blocks and continuously processes incoming alerts
        until interrupted or connection is lost.
        """
        url = f"{self.base_url}/api/v1/caregivers/alerts/stream"

        print(f"Connecting to {url}...")
        print("Waiting for alerts... (Press Ctrl+C to stop)\n")

        try:
            with requests.get(url, headers=self.headers, stream=True, timeout=None) as response:
                response.raise_for_status()
                print(f"✓ Connected successfully (Status: {response.status_code})\n")

                for line in response.iter_lines():
                    if not line:
                        continue

                    decoded_line = line.decode("utf-8")

                    # Skip keepalive comments
                    if decoded_line.startswith(":"):
                        print(".", end="", flush=True)  # Show keepalive activity
                        continue

                    # Parse SSE data
                    if decoded_line.startswith("data: "):
                        alert_data = json.loads(decoded_line[6:])
                        self._handle_alert(alert_data)

        except requests.exceptions.HTTPError as e:
            print(f"\n✗ HTTP Error: {e}")
            if e.response.status_code == 401:
                print("  Authentication failed. Check your token.")
            elif e.response.status_code == 403:
                print("  Access forbidden. Ensure you have CAREGIVER role.")
            sys.exit(1)
        except requests.exceptions.ConnectionError:
            print("\n✗ Connection error. Is the server running?")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\n\n✓ Disconnected by user")
            sys.exit(0)
        except Exception as e:
            print(f"\n✗ Unexpected error: {e}")
            sys.exit(1)

    def _handle_alert(self, alert: dict[str, Any]) -> None:
        """
        Process an incoming alert.

        Args:
            alert: Alert data dictionary
        """
        event_type = alert.get("event", "unknown")

        if event_type == "alert":
            self._handle_new_alert(alert)
        elif event_type == "alert_escalated":
            self._handle_escalated_alert(alert)
        elif event_type == "ack":
            self._handle_acknowledgment(alert)
        else:
            print(f"\n⚠️  Unknown event type: {event_type}")
            print(json.dumps(alert, indent=2))

    def _handle_new_alert(self, alert: dict[str, Any]) -> None:
        """Handle a new alert."""
        print("\n" + "=" * 70)
        print(f"🚨 NEW ALERT - {alert.get('tier', 'UNKNOWN')} PRIORITY")
        print("=" * 70)
        print(f"Alert ID:     {alert.get('alert_id')}")
        print(f"Patient ID:   {alert.get('patient_id')}")
        print(f"Vital Type:   {alert.get('vital_type')}")
        print(f"Timestamp:    {self._format_timestamp(alert.get('timestamp'))}")

        # Show vital readings
        window = alert.get("vitals_window", [])
        if window:
            print(f"Readings:     {', '.join(f'{v:.1f}' for v in window)}")

        # Show threshold
        threshold = alert.get("threshold", {})
        if threshold:
            min_val = threshold.get("min")
            max_val = threshold.get("max")
            if min_val is not None and max_val is not None:
                print(f"Normal Range: {min_val:.1f} - {max_val:.1f}")

        # Show reasons
        reasons = alert.get("reasons", [])
        if reasons:
            print("\nReasons:")
            for reason in reasons:
                print(f"  • {reason}")

        # Show context if available
        context = alert.get("context", {})
        if context:
            print("\nContext:")
            for key, value in context.items():
                print(f"  {key}: {value}")

        print("=" * 70)

        # Prompt for acknowledgment
        self._prompt_acknowledgment(alert)

    def _handle_escalated_alert(self, alert: dict[str, Any]) -> None:
        """Handle an escalated alert."""
        print("\n" + "=" * 70)
        print(f"⚠️  ALERT ESCALATED - {alert.get('tier', 'UNKNOWN')} PRIORITY")
        print("=" * 70)
        print(f"Alert ID:     {alert.get('alert_id')}")
        print(f"Patient ID:   {alert.get('patient_id')}")
        print(f"Vital Type:   {alert.get('vital_type')}")
        print(f"Timestamp:    {self._format_timestamp(alert.get('timestamp'))}")
        print("\n⚠️  This alert was not acknowledged in time and has been escalated.")
        print("=" * 70)

    def _handle_acknowledgment(self, alert: dict[str, Any]) -> None:
        """Handle an alert acknowledgment."""
        print("\n" + "-" * 70)
        print("✓ ALERT ACKNOWLEDGED")
        print("-" * 70)
        print(f"Alert ID:       {alert.get('alert_id')}")
        print(f"Patient ID:     {alert.get('patient_id')}")
        print(f"Acknowledged By: {alert.get('acknowledged_by')}")
        print(f"Timestamp:      {self._format_timestamp(alert.get('timestamp'))}")

        status = alert.get("status")
        if status:
            print(f"Status:         {status}")

        note = alert.get("note")
        if note:
            print(f"Note:           {note}")

        print("-" * 70)

    def _prompt_acknowledgment(self, alert: dict[str, Any]) -> None:
        """
        Prompt user to acknowledge the alert.

        Args:
            alert: Alert data dictionary
        """
        print("\nTo acknowledge this alert, use:")
        alert_id = alert.get("alert_id")
        patient_id = alert.get("patient_id")
        print(
            f"  curl -X POST '{self.base_url}/api/v1/alerts/alerts/{alert_id}/acknowledge?patient_id={patient_id}' \\"
        )
        print(f"       -H 'Authorization: Bearer YOUR_TOKEN' \\")
        print(f"       -H 'Content-Type: application/json' \\")
        print(f"       -d '{{\"status\": \"resolved\", \"note\": \"Patient contacted\"}}'")

    @staticmethod
    def _format_timestamp(timestamp: str | None) -> str:
        """
        Format ISO timestamp for display.

        Args:
            timestamp: ISO format timestamp string

        Returns:
            Formatted timestamp string
        """
        if not timestamp:
            return "N/A"

        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
        except (ValueError, AttributeError):
            return timestamp


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Stream caregiver alerts via SSE",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using command line argument
  python caregiver_alert_client.py --token eyJhbGc...
  
  # Using environment variable
  export CAREGIVER_TOKEN=eyJhbGc...
  python caregiver_alert_client.py
  
  # Custom API URL
  python caregiver_alert_client.py --url https://api.example.com --token eyJhbGc...
        """,
    )

    parser.add_argument(
        "--url",
        default=os.getenv("API_URL", "http://localhost:8000"),
        help="Base URL of the API (default: http://localhost:8000 or $API_URL)",
    )

    parser.add_argument(
        "--token",
        default=os.getenv("CAREGIVER_TOKEN"),
        help="JWT authentication token (or set $CAREGIVER_TOKEN)",
    )

    args = parser.parse_args()

    if not args.token:
        print("Error: Authentication token required")
        print("Provide via --token argument or CAREGIVER_TOKEN environment variable")
        sys.exit(1)

    client = CaregiverAlertClient(base_url=args.url, token=args.token)
    client.stream_alerts()


if __name__ == "__main__":
    main()
