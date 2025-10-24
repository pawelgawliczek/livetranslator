#!/bin/bash
# Install Git hooks for test enforcement

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}📌 Installing Git hooks...${NC}"
echo ""

cd "$(git rev-parse --show-toplevel)"

# Make hooks executable
chmod +x scripts/test/hooks/pre-commit
chmod +x scripts/test/hooks/pre-push
chmod +x scripts/test/hooks/commit-msg

# Copy hooks to .git/hooks
cp scripts/test/hooks/pre-commit .git/hooks/pre-commit
cp scripts/test/hooks/pre-push .git/hooks/pre-push
cp scripts/test/hooks/commit-msg .git/hooks/commit-msg

echo -e "${GREEN}✅ Git hooks installed!${NC}"
echo ""
echo "Hooks installed:"
echo "  • pre-commit: Runs unit tests (<30s)"
echo "  • pre-push: Runs full test suite (5-10min)"
echo "  • commit-msg: Validates commit message format"
echo ""
echo "To skip hooks (not recommended):"
echo "  git commit --no-verify"
echo "  git push --no-verify"
echo ""
