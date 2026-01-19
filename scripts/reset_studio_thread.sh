#!/bin/bash
# Reset LangGraph Studio thread checkpoints

echo "Stopping LangGraph Studio..."
pkill -f "langgraph dev"
sleep 2

echo "Clearing checkpoint storage..."
rm -rf .langgraph/checkpoints 2>/dev/null || true
rm -rf __pycache__ 2>/dev/null || true
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

echo "Restarting LangGraph Studio..."
langgraph dev
