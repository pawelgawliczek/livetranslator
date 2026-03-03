# Git hooks

Automated testing on commit. Install with `./setup-git-hooks.sh`.

## Pre-commit hook

Runs tests before each commit. If tests fail, the commit is blocked.

### Test levels

```bash
TEST_LEVEL=fast git commit -m "message"      # Unit tests only (~10s)
git commit -m "message"                       # Unit + Integration (~30s, default)
TEST_LEVEL=full git commit -m "message"       # All tests (~2-3min)
git commit --no-verify -m "message"           # Skip (emergency only)
```

| Level | Unit | Integration | E2E | Time |
|-------|------|-------------|-----|------|
| fast | yes | no | no | ~10s |
| standard | yes | yes | no | ~30s |
| full | yes | yes | yes | ~2-3m |

### Set a default

```bash
echo 'export TEST_LEVEL=fast' >> ~/.bashrc && source ~/.bashrc
```

## Commit-msg hook

Validates commit messages include a Feature ID for metrics tracking.

Valid formats: `[Feature-ID-10]`, `[Feature-10]`, `[FID-10]`, `[#10]`

Merge commits and reverts are exempt. Use `[no-feature-id]` for emergencies.

## Troubleshooting

```bash
# Reinstall hooks
./setup-git-hooks.sh

# Check hook is executable
ls -la .git/hooks/pre-commit

# Run tests manually
docker compose exec api pytest api/tests/ -v
```
