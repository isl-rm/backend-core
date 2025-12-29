#!/usr/bin/env python3
"""
Script to send test alerts to the alert system.

This script can be used to:
1. Listen to SSE alerts (as a client)
2. Send test vitals that trigger alerts
3. Manually broadcast alerts through the manager

Usage:
    # Listen to alerts
    python scripts/test_alert_sender.py listen --role caregiver --patient-id <patient_id>
    
    # Send a test vital that triggers an alert
    python scripts/test_alert_sender.py send-vital --patient-id <patient_id> --vital-type heart_rate --value 150
    
    # Send a manual alert
    python scripts/test_alert_sender.py send-alert --patient-id <patient_id> --role caregiver
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import typer

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

app = typer.Typer()

# Default configuration
BASE_URL = "http://localhost:8000"
DEFAULT_TOKEN = None  # Will be fetched via login


async def get_auth_token(email: str = "test@example.com", password: str = "password123") -> str:
    """Get authentication token by logging in."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": email, "password": password}
        )
        if response.status_code != 200:
            typer.echo(f"❌ Login failed: {response.text}", err=True)
            raise typer.Exit(1)
        
        data = response.json()
        return data["access_token"]


@app.command()
def listen(
    role: str = typer.Option("caregiver", help="Role to listen as (caregiver, doctor, nurse, admin)"),
    patient_id: str = typer.Option(None, help="Patient ID to monitor (use '*' for all patients)"),
    email: str = typer.Option("test@example.com", help="Email for authentication"),
    password: str = typer.Option("password123", help="Password for authentication"),
):
    """Listen to SSE alert stream."""
    asyncio.run(_listen(role, patient_id, email, password))


async def _listen(role: str, patient_id: str | None, email: str, password: str) -> None:
    """Async implementation of listen command."""
    typer.echo(f"🔐 Authenticating as {email}...")
    token = await get_auth_token(email, password)
    
    # Build URL
    url = f"{BASE_URL}/api/v1/alerts/stream?role={role}"
    if patient_id:
        url += f"&patient_id={patient_id}"
    
    typer.echo(f"📡 Connecting to SSE stream: {url}")
    typer.echo(f"👤 Role: {role}")
    typer.echo(f"🏥 Patient ID: {patient_id or 'own ID (patient role)'}")
    typer.echo("⏳ Waiting for alerts... (Press Ctrl+C to stop)\n")
    
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "GET",
                url,
                headers={"Authorization": f"Bearer {token}"}
            ) as response:
                if response.status_code != 200:
                    typer.echo(f"❌ Connection failed: {response.status_code}", err=True)
                    typer.echo(f"Response: {await response.aread()}", err=True)
                    return
                
                typer.echo(f"✅ Connected! Status: {response.status_code}\n")
                
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    
                    if line.startswith(":"):
                        # Keepalive comment
                        typer.echo(f"💓 Keepalive: {line}")
                    elif line.startswith("data:"):
                        # Alert data
                        data_str = line[5:].strip()
                        try:
                            alert_data = json.loads(data_str)
                            typer.echo("🚨 " + "=" * 60)
                            typer.echo(f"🚨 ALERT RECEIVED at {datetime.now().isoformat()}")
                            typer.echo("🚨 " + "=" * 60)
                            typer.echo(f"Alert ID: {alert_data.get('alert_id')}")
                            typer.echo(f"Tier: {alert_data.get('tier')}")
                            typer.echo(f"Patient ID: {alert_data.get('patient_id')}")
                            typer.echo(f"Vital Type: {alert_data.get('vital_type')}")
                            typer.echo(f"Values: {alert_data.get('vitals_window')}")
                            typer.echo(f"Threshold: {alert_data.get('threshold')}")
                            typer.echo(f"Reasons: {alert_data.get('reasons')}")
                            typer.echo(f"Recipients: {alert_data.get('recipients')}")
                            typer.echo("=" * 60 + "\n")
                        except json.JSONDecodeError:
                            typer.echo(f"📨 Data: {data_str}")
                    else:
                        typer.echo(f"📨 {line}")
                        
    except KeyboardInterrupt:
        typer.echo("\n\n👋 Disconnected by user")
    except Exception as e:
        typer.echo(f"\n❌ Error: {e}", err=True)
        raise


@app.command()
def send_vital(
    patient_id: str = typer.Option(..., help="Patient ID"),
    vital_type: str = typer.Option("heart_rate", help="Vital type (heart_rate, blood_pressure, etc.)"),
    value: float = typer.Option(..., help="Vital value (e.g., 150 for high heart rate)"),
    email: str = typer.Option("test@example.com", help="Email for authentication"),
    password: str = typer.Option("password123", help="Password for authentication"),
):
    """Send a vital reading that may trigger an alert."""
    asyncio.run(_send_vital(patient_id, vital_type, value, email, password))


async def _send_vital(patient_id: str, vital_type: str, value: float, email: str, password: str) -> None:
    """Async implementation of send_vital command."""
    typer.echo(f"🔐 Authenticating as {email}...")
    token = await get_auth_token(email, password)
    
    # Create vital payload
    vital_data = {
        "type": vital_type,
        "value": value,
        "unit": "bpm" if vital_type == "heart_rate" else "mmHg",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    typer.echo(f"📊 Sending vital to patient {patient_id}:")
    typer.echo(f"   Type: {vital_type}")
    typer.echo(f"   Value: {value}")
    
    async with httpx.AsyncClient() as client:
        # Send via WebSocket endpoint (simulating mobile device)
        # Note: This requires WebSocket support, so we'll use HTTP endpoint instead
        response = await client.post(
            f"{BASE_URL}/api/v1/vitals",
            headers={"Authorization": f"Bearer {token}"},
            json=vital_data
        )
        
        if response.status_code in [200, 201]:
            typer.echo(f"✅ Vital sent successfully!")
            typer.echo(f"Response: {response.json()}")
        else:
            typer.echo(f"❌ Failed to send vital: {response.status_code}", err=True)
            typer.echo(f"Response: {response.text}", err=True)


@app.command()
def send_alert(
    patient_id: str = typer.Option(..., help="Patient ID"),
    role: str = typer.Option("caregiver", help="Role to send alert to"),
    tier: str = typer.Option("CRITICAL", help="Alert tier (CRITICAL, WARNING, INFO)"),
    vital_type: str = typer.Option("heart_rate", help="Vital type"),
    message: str = typer.Option("Test alert", help="Alert message"),
):
    """Send a manual test alert directly through the manager."""
    asyncio.run(_send_alert(patient_id, role, tier, vital_type, message))


async def _send_alert(patient_id: str, role: str, tier: str, vital_type: str, message: str) -> None:
    """Async implementation of send_alert command."""
    # This requires direct access to the alert manager
    # We'll need to import it from the running application
    
    typer.echo("⚠️  Manual alert sending requires direct access to the application.")
    typer.echo("This feature is best used within the application context.")
    typer.echo("\nTo manually trigger an alert, you can:")
    typer.echo("1. Send high/low vital values using 'send-vital' command")
    typer.echo("2. Use the WebSocket endpoint to stream vitals")
    typer.echo("3. Create a custom script that imports the alert manager")


@app.command()
def test_connection(
    email: str = typer.Option("test@example.com", help="Email for authentication"),
    password: str = typer.Option("password123", help="Password for authentication"),
):
    """Test connection to the API and authentication."""
    asyncio.run(_test_connection(email, password))


async def _test_connection(email: str, password: str) -> None:
    """Test API connection."""
    typer.echo(f"🔍 Testing connection to {BASE_URL}...")
    
    async with httpx.AsyncClient() as client:
        # Test health endpoint
        try:
            response = await client.get(f"{BASE_URL}/health")
            typer.echo(f"✅ Health check: {response.status_code}")
        except Exception as e:
            typer.echo(f"❌ Health check failed: {e}", err=True)
            return
        
        # Test authentication
        try:
            token = await get_auth_token(email, password)
            typer.echo(f"✅ Authentication successful")
            typer.echo(f"Token (first 20 chars): {token[:20]}...")
        except Exception as e:
            typer.echo(f"❌ Authentication failed: {e}", err=True)
            return
        
        typer.echo("\n✅ All tests passed!")


if __name__ == "__main__":
    app()
