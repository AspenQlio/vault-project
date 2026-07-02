#!/bin/bash

# Enter the project directory
cd ~/vault-project

# Activate virtual environment
source venv/bin/activate

# Start the server in the background and save its process ID (PID)
uvicorn server.main:app > /dev/null 2>&1 &
SERVER_PID=$!

# Give the server 1 second to start before opening the interface
sleep 1

# Start the graphical interface
python client/main.py

# When closing the graphical window, kill the server process
kill $SERVER_PID
