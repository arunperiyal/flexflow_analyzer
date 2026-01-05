#!/bin/bash
# Test Phase 4 - Domain-Driven Structure

echo "Testing Phase 4 - Domain-Driven Structure"
echo "==========================================="
echo ""

PASSED=0
FAILED=0

# Function to test a command
test_command() {
    local desc="$1"
    local cmd="$2"
    echo -n "Testing: $desc ... "
    if eval "$cmd" > /dev/null 2>&1; then
        echo "PASS"
        ((PASSED++))
    else
        echo "FAIL"
        ((FAILED++))
    fi
}

echo "Testing new domain-driven commands..."
echo ""

# Case commands
test_command "case --help" "python main.py case --help"
test_command "case show CS4SG1U1" "python main.py case show CS4SG1U1"

# Data commands
test_command "data --help" "python main.py data --help"
test_command "data show CS4SG1U1 --node 24" "python main.py data show CS4SG1U1 --node 24"

# Field commands  
test_command "field --help" "python main.py field --help"
test_command "field info CS4SG1U1" "python main.py field info CS4SG1U1"

# Config commands
test_command "config --help" "python main.py config --help"

echo ""
echo "Testing backward compatibility (old commands still work)..."
echo ""

# Old commands should still work
test_command "info CS4SG1U1" "python main.py info CS4SG1U1"
test_command "preview CS4SG1U1 --node 24" "python main.py preview CS4SG1U1 --node 24"
test_command "tecplot info CS4SG1U1" "python main.py tecplot info CS4SG1U1"

echo ""
echo "==========================================="
echo "Test Results"
echo "==========================================="
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✓ Phase 4 implementation successful!"
    echo "Both old and new command structures working."
    exit 0
else
    echo "✗ Some tests failed"
    exit 1
fi
