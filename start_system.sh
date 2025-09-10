#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting AcompanhAR Multi-Container System${NC}"
echo -e "${YELLOW}==============================================${NC}"

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    echo -e "${YELLOW}📝 Creating .env from template...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}⚠️  Please edit .env file with your GEMINI_API_KEY${NC}"
    exit 1
fi

# Check if GEMINI_API_KEY is set
source .env
if [ -z "$GEMINI_API_KEY" ] || [ "$GEMINI_API_KEY" = "your_gemini_api_key_here" ]; then
    echo -e "${RED}❌ GEMINI_API_KEY not set in .env file!${NC}"
    echo -e "${YELLOW}⚠️  Please edit .env file with your actual Gemini API key${NC}"
    exit 1
fi

# Create necessary directories
echo -e "${GREEN}📁 Creating directories...${NC}"
mkdir -p messages audio_files media_files logs results

# Make scripts executable
chmod +x *.sh

# Stop any existing containers
echo -e "${YELLOW}🛑 Stopping existing containers...${NC}"
docker-compose down 2>/dev/null

# Build and start containers
echo -e "${GREEN}🏗️  Building and starting containers...${NC}"
docker-compose up --build -d

# Function to check container health
check_health() {
    local service_name=$1
    local url=$2
    local max_attempts=30
    local attempt=1
    
    echo -e "${BLUE}🔍 Checking $service_name health...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ $service_name is healthy!${NC}"
            return 0
        fi
        echo -e "${YELLOW}⏳ Waiting for $service_name... (attempt $attempt/$max_attempts)${NC}"
        sleep 2
        ((attempt++))
    done
    
    echo -e "${RED}❌ $service_name failed to start properly${NC}"
    return 1
}

# Wait for services to be ready
echo -e "\n${BLUE}🏥 Checking service health...${NC}"

# Check API (Container A)
check_health "API Service" "http://localhost:8000/health"

# Check WhatsApp Monitor (Container B)  
check_health "WhatsApp Monitor" "http://localhost:3000/health"

# Show container status
echo -e "\n${PURPLE}📊 Container Status:${NC}"
docker-compose ps

# Show logs for WhatsApp container to display QR code
echo -e "\n${GREEN}📱 WhatsApp QR Code:${NC}"
echo -e "${YELLOW}Scan the QR code below with your WhatsApp mobile app:${NC}"
echo -e "${YELLOW}========================================${NC}"

# Follow WhatsApp logs to show QR code
docker-compose logs -f acompanhar-whatsapp &
LOGS_PID=$!

# Function to handle cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}🛑 Stopping services...${NC}"
    kill $LOGS_PID 2>/dev/null
    docker-compose down
    echo -e "${GREEN}✅ System stopped${NC}"
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

echo -e "\n${BLUE}🎯 System Information:${NC}"
echo -e "${GREEN}📖 API Documentation: http://localhost:8000/docs${NC}"
echo -e "${GREEN}⚡ API Health: http://localhost:8000/health${NC}"
echo -e "${GREEN}📊 Reports List: http://localhost:8000/reports/list${NC}"
echo -e "${GREEN}💬 WhatsApp Health: http://localhost:3000/health${NC}"
echo -e "\n${YELLOW}📱 Instructions:${NC}"
echo -e "1. Scan the QR code with WhatsApp"
echo -e "2. Send any message to start using the system"
echo -e "3. Follow the prompts for PIN and data collection"
echo -e "\n${YELLOW}Press Ctrl+C to stop all services${NC}"
echo -e "${YELLOW}========================================${NC}"

# Keep script running
wait