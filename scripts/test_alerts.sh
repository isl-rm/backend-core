#!/bin/bash
# Test Alert System - Quick Start Guide
# ======================================

echo "🚨 Alert System Test Scripts"
echo "=============================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="http://localhost:8000"
EMAIL="test@example.com"
PASSWORD="password123"

# Function to get auth token
get_token() {
    echo -e "${YELLOW}🔐 Getting authentication token...${NC}"
    TOKEN=$(curl -s -X POST "${BASE_URL}/api/v1/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}" \
        | grep -o '"access_token":"[^"]*' \
        | cut -d'"' -f4)
    
    if [ -z "$TOKEN" ]; then
        echo -e "${RED}❌ Failed to get token. Make sure the server is running and credentials are correct.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Token obtained${NC}"
    echo ""
}

# Function to listen to SSE alerts
listen_alerts() {
    local ROLE=${1:-caregiver}
    local PATIENT_ID=${2:-test-patient-123}
    
    echo -e "${YELLOW}📡 Connecting to SSE alert stream...${NC}"
    echo "   Role: $ROLE"
    echo "   Patient ID: $PATIENT_ID"
    echo "   Press Ctrl+C to stop"
    echo ""
    
    curl -N -H "Authorization: Bearer ${TOKEN}" \
        "${BASE_URL}/api/v1/alerts/stream?role=${ROLE}&patient_id=${PATIENT_ID}"
}

# Function to send a test vital
send_vital() {
    local PATIENT_ID=${1:-test-patient-123}
    local VITAL_TYPE=${2:-heart_rate}
    local VALUE=${3:-150}
    
    echo -e "${YELLOW}📊 Sending vital reading...${NC}"
    echo "   Patient ID: $PATIENT_ID"
    echo "   Type: $VITAL_TYPE"
    echo "   Value: $VALUE"
    echo ""
    
    RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/vitals" \
        -H "Authorization: Bearer ${TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{
            \"type\":\"${VITAL_TYPE}\",
            \"value\":${VALUE},
            \"unit\":\"bpm\",
            \"timestamp\":\"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\"
        }")
    
    echo -e "${GREEN}✅ Response:${NC}"
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    echo ""
}

# Main menu
show_menu() {
    echo ""
    echo "Choose an option:"
    echo "  1) Listen to alerts (SSE stream)"
    echo "  2) Send test vital (may trigger alert)"
    echo "  3) Send manual alert (using Python script)"
    echo "  4) Test connection"
    echo "  5) Exit"
    echo ""
    read -p "Enter choice [1-5]: " choice
    
    case $choice in
        1)
            get_token
            read -p "Enter role (default: caregiver): " role
            role=${role:-caregiver}
            read -p "Enter patient ID (default: test-patient-123): " patient_id
            patient_id=${patient_id:-test-patient-123}
            listen_alerts "$role" "$patient_id"
            ;;
        2)
            get_token
            read -p "Enter patient ID (default: test-patient-123): " patient_id
            patient_id=${patient_id:-test-patient-123}
            read -p "Enter vital type (default: heart_rate): " vital_type
            vital_type=${vital_type:-heart_rate}
            read -p "Enter value (default: 150): " value
            value=${value:-150}
            send_vital "$patient_id" "$vital_type" "$value"
            show_menu
            ;;
        3)
            echo -e "${YELLOW}Running Python script to send manual alert...${NC}"
            python3 scripts/send_test_alert.py
            show_menu
            ;;
        4)
            get_token
            echo -e "${GREEN}✅ Connection successful!${NC}"
            show_menu
            ;;
        5)
            echo "Goodbye!"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            show_menu
            ;;
    esac
}

# Check if server is running
echo -e "${YELLOW}Checking if server is running...${NC}"
if ! curl -s "${BASE_URL}/health" > /dev/null 2>&1; then
    echo -e "${RED}❌ Server is not running at ${BASE_URL}${NC}"
    echo "Please start the server with: docker compose up"
    exit 1
fi
echo -e "${GREEN}✅ Server is running${NC}"

# Show menu
show_menu
