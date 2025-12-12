#!/bin/bash
# =============================================================================
# CCU Environment Variables Setup Script
# =============================================================================
# This script sets environment variables for CCU connection.
#
# Usage:
#   source script/set_ccu_env.sh
#
# After sourcing, you can run:
#   python example_state_machine_test.py
#
# =============================================================================

# Required variables - UPDATE THESE FOR YOUR CCU
export CCU_HOST="192.168.178.116"
export CCU_USERNAME="Admin"
export CCU_PASSWORD="admin"

# Optional variables (defaults shown)
export CCU_PORT_HMIP="2010"
export CCU_PORT_BIDCOS="2001"
export CCU_CALLBACK_PORT="54323"

# =============================================================================
# Verification
# =============================================================================
echo "CCU Environment Variables Set:"
echo "  CCU_HOST         = $CCU_HOST"
echo "  CCU_USERNAME     = $CCU_USERNAME"
echo "  CCU_PASSWORD     = ********"
echo "  CCU_PORT_HMIP    = $CCU_PORT_HMIP"
echo "  CCU_PORT_BIDCOS  = $CCU_PORT_BIDCOS"
echo "  CCU_CALLBACK_PORT = $CCU_CALLBACK_PORT"
echo ""
echo "You can now run: python example_state_machine_test.py"
