#!/bin/bash

# ================================
# Multi-Agent Production Job Optimizer
# Setup Script for Linux/Mac
# ================================

echo ""
echo "===================================================="
echo " Multi-Agent Production Job Optimizer - Setup"
echo "===================================================="
echo ""

# Check Python installation
if ! command -v python3 &> /dev/null
then
    echo "ERROR: Python3 is not installed"
    echo "Please install Python 3.10 or higher"
    exit 1
fi

echo "[1/5] Checking Python installation..."
python3 --version
echo ""

# Create virtual environment
echo "[2/5] Creating virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists. Skipping creation."
else
    python3 -m venv venv
    echo "Virtual environment created successfully!"
fi
echo ""

# Activate virtual environment
echo "[3/5] Activating virtual environment..."
source venv/bin/activate
echo ""

# Install dependencies
echo "[4/5] Installing dependencies (this may take a few minutes)..."
pip install --upgrade pip
pip install -r requirements.txt
echo ""

# Check for .env file
echo "[5/5] Checking environment configuration..."
if [ -f ".env" ]; then
    echo ".env file already exists."
else
    if [ -f ".env.template" ]; then
        cp .env.template .env
        echo ""
        echo "IMPORTANT: .env file created from template."
        echo "Please edit .env and add your API keys:"
        echo "  - GROQ_API_KEY"
        echo "  - LANGCHAIN_API_KEY"
        echo ""
    else
        echo "WARNING: .env.template not found!"
    fi
fi

echo ""
echo "===================================================="
echo " Setup Complete!"
echo "===================================================="
echo ""
echo "NEXT STEPS:"
echo ""
echo "1. Edit .env file and add your API keys:"
echo "   - Get Groq API key from: https://console.groq.com"
echo "   - Get LangSmith key from: https://smith.langchain.com"
echo ""
echo "2. Generate test data:"
echo "   python -m utils.data_generator"
echo ""
echo "3. Run the Streamlit dashboard:"
echo "   streamlit run ui/app.py"
echo ""
echo "4. Or test the orchestrator directly:"
echo "   python workflows/orchestrator.py"
echo ""
echo "===================================================="
echo ""
