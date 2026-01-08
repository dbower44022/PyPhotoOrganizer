#!/bin/bash
# PyPhotoOrganizer Test Runner
# Convenient script for running tests with common options

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}PyPhotoOrganizer Test Runner${NC}"
echo "=============================="
echo ""

# Function to display usage
usage() {
    echo "Usage: ./run_tests.sh [option]"
    echo ""
    echo "Options:"
    echo "  all          - Run all tests (default)"
    echo "  unit         - Run only unit tests"
    echo "  integration  - Run only integration tests"
    echo "  database     - Run only database tests"
    echo "  fast         - Run tests excluding slow ones"
    echo "  coverage     - Run tests with coverage report"
    echo "  example      - Run example tests only"
    echo "  install      - Install test dependencies"
    echo "  help         - Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./run_tests.sh all"
    echo "  ./run_tests.sh unit"
    echo "  ./run_tests.sh coverage"
    exit 1
}

# Parse command line argument
TEST_TYPE="${1:-all}"

case "$TEST_TYPE" in
    all)
        echo -e "${GREEN}Running all tests...${NC}"
        pytest -v
        ;;

    unit)
        echo -e "${GREEN}Running unit tests...${NC}"
        pytest tests/unit/ -v
        ;;

    integration)
        echo -e "${GREEN}Running integration tests...${NC}"
        pytest tests/integration/ -v
        ;;

    database)
        echo -e "${GREEN}Running database tests...${NC}"
        pytest tests/database/ -v
        ;;

    fast)
        echo -e "${GREEN}Running fast tests (excluding slow tests)...${NC}"
        pytest -m "not slow" -v
        ;;

    coverage)
        echo -e "${GREEN}Running tests with coverage report...${NC}"
        pytest --cov=. --cov-report=html --cov-report=term
        echo ""
        echo -e "${YELLOW}Coverage report generated in: htmlcov/index.html${NC}"
        ;;

    example)
        echo -e "${GREEN}Running example tests...${NC}"
        pytest tests/test_example.py -v
        ;;

    install)
        echo -e "${GREEN}Installing test dependencies...${NC}"
        pip install pytest pytest-cov pytest-timeout
        echo ""
        echo -e "${GREEN}Test dependencies installed successfully!${NC}"
        ;;

    help|--help|-h)
        usage
        ;;

    *)
        echo -e "${YELLOW}Unknown option: $TEST_TYPE${NC}"
        echo ""
        usage
        ;;
esac

echo ""
echo -e "${BLUE}Test run complete!${NC}"
