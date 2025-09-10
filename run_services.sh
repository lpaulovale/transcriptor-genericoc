#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting AcompanhAR System${NC}"
echo -e "${YELLOW}================================${NC}"

# Function to handle cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}🛑 Shutting down services...${NC}"
    kill $FASTAPI_PID $WHATSAPP_PID 2>/dev/null
    wait
    echo -e "${GREEN}✅ Services stopped${NC}"
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Activate Python virtual environment
source /opt/venv/bin/activate

# Start FastAPI backend in background
echo -e "${GREEN}🐍 Starting FastAPI backend...${NC}"
python main.py &
FASTAPI_PID=$!

# Wait a bit for FastAPI to start
sleep 3

# Start WhatsApp monitor in background
echo -e "${GREEN}💬 Starting WhatsApp monitor...${NC}"
node whatsapp_monitor.js &
WHATSAPP_PID=$!

# Wait for both processes
echo -e "${BLUE}📱 System is running!${NC}"
echo -e "${YELLOW}Scan the QR code to connect WhatsApp${NC}"
echo -e "${YELLOW}FastAPI docs: http://localhost:8000/docs${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo -e "${YELLOW}================================${NC}"

wait