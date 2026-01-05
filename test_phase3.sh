#!/bin/bash
# Phase 3 Testing - Verify activated architecture

echo "==========================================="
echo "Phase 3: Production Activation Testing"
echo "==========================================="
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
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
        ((FAILED++))
        return 1
    fi
}

echo "Testing activated main.py (was main_v2.py)..."
echo ""

# Core functionality tests
test_command "Main help" "python main.py --help"
test_command "Info command" "python main.py info CS4SG1U1"
test_command "Preview command" "python main.py preview CS4SG1U1 --node 24"
test_command "Statistics command" "python main.py statistics CS4SG1U1 --node 24"

echo ""
echo "Testing all command help pages..."
echo ""

test_command "info --help" "python main.py info --help"
test_command "new --help" "python main.py new --help"
test_command "plot --help" "python main.py plot --help"
test_command "compare --help" "python main.py compare --help"
test_command "preview --help" "python main.py preview --help"
test_command "statistics --help" "python main.py statistics --help"
test_command "template --help" "python main.py template --help"
test_command "docs --help" "python main.py docs --help"
test_command "tecplot --help" "python main.py tecplot --help"

echo ""
echo "Testing command examples..."
echo ""

test_command "info --examples" "python main.py info --examples"
test_command "new --examples" "python main.py new --examples"
test_command "plot --examples" "python main.py plot --examples"
test_command "compare --examples" "python main.py compare --examples"

echo ""
echo "Verification: Check that old main is backed up..."
echo ""

if [ -f "main_old.py" ]; then
    echo -e "${GREEN}✓ Backup exists: main_old.py${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Backup missing: main_old.py${NC}"
    ((FAILED++))
fi

if [ -f "main.py" ]; then
    echo -e "${GREEN}✓ New main.py active${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ main.py missing${NC}"
    ((FAILED++))
fi

# Check that new main.py is the registry version
if grep -q "registry.register" main.py; then
    echo -e "${GREEN}✓ main.py uses registry pattern${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ main.py doesn't use registry pattern${NC}"
    ((FAILED++))
fi

echo ""
echo "==========================================="
echo "Test Results"
echo "==========================================="
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ Phase 3 activation successful!${NC}"
    echo "New architecture is live and fully functional."
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
