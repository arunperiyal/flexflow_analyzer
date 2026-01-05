#!/bin/bash
# Phase 2 Testing Script - Test all migrated commands

echo "==========================================="
echo "Phase 2: All Commands Migration Testing"
echo "==========================================="
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

PASSED=0
FAILED=0

test_command() {
    local desc=$1
    local cmd=$2
    
    echo -n "Testing: $desc ... "
    
    output=$(eval "$cmd" 2>&1)
    exit_code=$?
    
    if [ $exit_code -eq 0 ] && [ ! -z "$output" ]; then
        echo -e "${GREEN}PASS${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        echo "  Exit code: $exit_code"
        echo "  Output length: ${#output}"
        ((FAILED++))
        return 1
    fi
}

echo "Testing all commands..."
echo ""

# Test each command's help
test_command "info --help" "python main_v2.py info --help"
test_command "new --help" "python main_v2.py new --help"
test_command "plot --help" "python main_v2.py plot --help"
test_command "compare --help" "python main_v2.py compare --help"
test_command "preview --help" "python main_v2.py preview --help"
test_command "statistics --help" "python main_v2.py statistics --help"
test_command "template --help" "python main_v2.py template --help"
test_command "docs --help" "python main_v2.py docs --help"
test_command "tecplot --help" "python main_v2.py tecplot --help"

echo ""
echo "Testing command examples..."
echo ""

# Test examples where available
test_command "info --examples" "python main_v2.py info --examples"
test_command "new --examples" "python main_v2.py new --examples"
test_command "plot --examples" "python main_v2.py plot --examples"
test_command "compare --examples" "python main_v2.py compare --examples"

echo ""
echo "Testing actual execution..."
echo ""

# Test actual execution
test_command "info CS4SG1U1" "python main_v2.py info CS4SG1U1"
test_command "preview CS4SG1U1 --node 24" "python main_v2.py preview CS4SG1U1 --node 24"
test_command "statistics CS4SG1U1 --node 24" "python main_v2.py statistics CS4SG1U1 --node 24"

echo ""
echo "==========================================="
echo "Test Results"
echo "==========================================="
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All Phase 2 tests passed!${NC}"
    echo "All 9 commands successfully migrated to registry pattern."
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
