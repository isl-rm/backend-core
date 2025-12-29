#!/usr/bin/env python3
"""
Quick script to send vitals via WebSocket and trigger alerts.
Run this to send high heart rate readings that will trigger an alert.
"""

import asyncio
import json
import sys
from pathlib import Path

import websockets

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

async def send_vitals_via_websocket(token: str, patient_id: str = None):
    """Send vitals via WebSocket to trigger alerts."""
    
    uri = f"ws://localhost:8000/api/v1/vitals/ws/mobile?token={token}"
    
    print(f"📡 Connecting to WebSocket: {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")
            print("📤 Sending 3 high heart rate readings...")
            
            # Send 3 consecutive high readings to trigger alert
            for i in range(1, 4):
                vital_data = {
                    "type": "heart_rate",
                    "value": 150 + (i * 5),  # 155, 160, 165
                    "unit": "bpm"
                }
                
                await websocket.send(json.dumps(vital_data))
                print(f"   Sent reading {i}: {vital_data['value']} bpm")
                await asyncio.sleep(0.5)
            
            print("\n✅ All vitals sent!")
            print("🚨 Alert should be triggered now (check your SSE listener)")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


async def get_token(email: str = "test@example.com", password: str = "password123") -> str:
    """Get auth token."""
    import httpx
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/auth/login",
            json={"email": email, "password": password}
        )
        
        if response.status_code != 200:
            print(f"❌ Login failed: {response.text}")
            sys.exit(1)
        
        return response.json()["access_token"]


async def main():
    print("=" * 60)
    print("🚨 WebSocket Vital Sender (Triggers Alerts)")
    print("=" * 60)
    print()
    
    # Get credentials
    email = input("Email (default: test@example.com): ").strip() or "test@example.com"
    password = input("Password (default: password123): ").strip() or "password123"
    
    print(f"\n🔐 Authenticating as {email}...")
    token = await get_token(email, password)
    print("✅ Authenticated!\n")
    
    await send_vitals_via_websocket(token)
    
    print("\n" + "=" * 60)
    print("💡 Make sure you have an SSE listener running in another terminal:")
    print("   curl -N -H 'Authorization: Bearer YOUR_TOKEN' \\")
    print("     'http://localhost:8000/api/v1/alerts/stream?role=patient&patient_id=*'")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
