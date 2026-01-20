#!/bin/bash

echo "======================================================================================================"
echo "LANGGRAPH STUDIO WITH LOG CAPTURE"
echo "======================================================================================================"
echo ""

# Set up log file
LOGFILE="studio_run_$(date +%Y%m%d_%H%M%S).log"
echo "Log file: $LOGFILE"
echo ""

# Start LangGraph Studio and capture logs
echo "Starting LangGraph Studio..."
echo "UI will open at: http://127.0.0.1:2024"
echo ""
echo "INSTRUCTIONS:"
echo "1. Create a NEW thread in the UI (don't reuse old threads!)"
echo "2. Enter your query and run the pipeline"
echo "3. When complete, press Ctrl+C here to stop and show logs"
echo ""
echo "======================================================================================================"
echo ""

# Run langgraph dev with full logging
langgraph dev --verbose 2>&1 | tee "$LOGFILE"

echo ""
echo "======================================================================================================"
echo "LANGGRAPH STUDIO STOPPED"
echo "======================================================================================================"
echo "Logs saved to: $LOGFILE"
echo ""
echo "To view logs:"
echo "  cat $LOGFILE"
echo "  grep 'test_plan' $LOGFILE"
echo "  grep 'orchestrator' $LOGFILE"
echo ""
