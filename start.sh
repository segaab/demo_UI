#!/bin/bash

# Start Redis
redis-server --port 6381 --daemonize yes

# Wait for Redis to be ready
sleep 2

# Start the RSS poller in the background
python rss_poller.py &

# Start the main application
python src/main.py 