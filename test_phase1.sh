#!/bin/bash
# Phase 1 Testing Script - Compare old vs new implementations

echo "==================================="
echo "Phase 1: Registry Pattern Testing"
echo "==================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

# Test function
test_command() {
    local desc=$1
    local cmd_old=$2
    local cmd_new=$3
    
    echo -n "Testing: $desc ... "
    
    output_old=$(eval "$cmd_old" 2>&1)
    output_new=$(eval "$cmd_new" 2>&1)
    
    if [ "$output_old" == "$output_new" ]; then
        echo -e "${GREEN}PASS${NC}"
        ((PASSED++))
    else
        echo -e "${RED}FAIL${NC}"
        echo "  Old output length: ${#output_old}"
        echo "  New output length: ${#output_new}"
        ((FAILED++))
    fi
}

echo "Running comparison tests..."
echo ""

# Test 1: Main help
test_command "Main help" \
    "python main.py --help" \
    "python main_v2.py --help"

# Test 2: Info help
test_command "Info command help" \
    "python main.py info --help" \
    "python main_v2.py info --help"

# Test 3: Info examples
test_command "Info command examples" \
    "python main.py info --examples" \
    "python main_v2.py info --examples"

# Test 4: Info execution
test_command "Info command execution" \
    "python main.py info CS4SG1U1" \
    "python main_v2.py info CS4SG1U1"

# Test 5: Invalid command
test_command "Invalid command handling" \
    "python main.py invalid 2>&1" \
    "python main_v2.py invalid 2>&1"

echo ""
echo "==================================="
echo "Test Results"
echo "==================================="
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo "The new registry pattern is working correctly."
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    echo "Review the differences above."
    exit 1
fi
