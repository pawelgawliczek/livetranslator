#!/bin/bash
#
# Git Hooks Setup Script
# Installs pre-commit hooks for LiveTranslator
#

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}🔧 Setting up git hooks for LiveTranslator...${NC}"
echo ""

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "❌ Error: Not in a git repository"
    echo "Run this script from the project root directory"
    exit 1
fi

# Create hooks directory if it doesn't exist
mkdir -p .git/hooks

# Copy pre-commit hook
echo "📋 Installing pre-commit hook..."
cp .git-hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

echo -e "${GREEN}✅ Pre-commit hook installed successfully!${NC}"
echo ""

# Display usage information
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Git Hooks Installed - Usage Guide${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""
echo "The pre-commit hook will automatically run tests before each commit."
echo ""
echo -e "${YELLOW}Test Levels:${NC}"
echo ""
echo "  1. Fast (unit tests only, ~10s):"
echo "     $ TEST_LEVEL=fast git commit -m \"message\""
echo ""
echo "  2. Standard (unit + integration, ~30s) [DEFAULT]:"
echo "     $ git commit -m \"message\""
echo ""
echo "  3. Full (unit + integration + E2E, ~2-3min):"
echo "     $ TEST_LEVEL=full git commit -m \"message\""
echo ""
echo "  4. Skip tests (use with caution!):"
echo "     $ git commit --no-verify -m \"message\""
echo "     OR"
echo "     $ TEST_LEVEL=skip git commit -m \"message\""
echo ""
echo -e "${YELLOW}Quick Tips:${NC}"
echo ""
echo "  • Use 'fast' for quick iterations during development"
echo "  • Use 'standard' for most commits (default)"
echo "  • Use 'full' before pushing or for important commits"
echo "  • --no-verify should only be used in emergencies"
echo ""
echo -e "${YELLOW}Set default test level (optional):${NC}"
echo ""
echo "  Add to your ~/.bashrc or ~/.zshrc:"
echo "    export TEST_LEVEL=fast   # Use fast tests by default"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}🎉 Setup complete! Your commits will now run tests automatically.${NC}"
echo ""
