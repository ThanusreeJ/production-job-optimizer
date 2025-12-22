@echo off
REM ================================
REM Multi-Agent Production Job Optimizer
REM Setup Script for Windows
REM ================================

echo.
echo ====================================================
echo  Multi-Agent Production Job Optimizer - Setup
echo ====================================================
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10 or higher from: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/5] Checking Python installation...
python --version
echo.

REM Create virtual environment
echo [2/5] Creating virtual environment...
if exist venv (
    echo Virtual environment already exists. Skipping creation.
) else (
    python -m venv venv
    echo Virtual environment created successfully!
)
echo.

REM Activate virtual environment
echo [3/5] Activating virtual environment...
call venv\Scripts\activate.bat
echo.

REM Install dependencies
echo [4/5] Installing dependencies (this may take a few minutes)...
pip install --upgrade pip
pip install -r requirements.txt
echo.

REM Check for .env file
echo [5/5] Checking environment configuration...
if exist .env (
    echo .env file already exists.
) else (
    if exist .env.template (
        copy .env.template .env
        echo.
        echo IMPORTANT: .env file created from template.
        echo Please edit .env and add your API keys:
        echo   - GROQ_API_KEY
        echo   - LANGCHAIN_API_KEY
        echo.
    ) else (
        echo WARNING: .env.template not found!
    )
)

echo.
echo ====================================================
echo  Setup Complete!
echo ====================================================
echo.
echo NEXT STEPS:
echo.
echo 1. Edit .env file and add your API keys:
echo    - Get Groq API key from: https://console.groq.com
echo    - Get LangSmith key from: https://smith.langchain.com
echo.
echo 2. Generate test data:
echo    python -m utils.data_generator
echo.
echo 3. Run the Streamlit dashboard:
echo    streamlit run ui/app.py
echo.
echo 4. Or test the orchestrator directly:
echo    python workflows/orchestrator.py
echo.
echo ====================================================
echo.
pause
