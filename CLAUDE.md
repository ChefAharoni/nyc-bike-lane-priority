@AGENTS.md

## Notes for Claude Code

- Begin every session by reading `AGENTS.md` (imported above) and the doc for the area you are touching: `docs/data-contract.md` for data, `docs/operations.md` for the workflow and deploy.
- Run `scripts/check_branding.sh` before every commit and never print or quote the banned-terms list.
- Verify map and layout changes in a real browser with real data (Playwright is installed in `site/`; use `channel: 'chrome'`), on desktop and at 390 x 844.
- Ask before outward-facing actions the user hasn't requested: changing repository settings or secrets, DNS, force-pushing, or deleting the `data` branch.
