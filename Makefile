.PHONY: install sim login verify test clean

install:
	pip install -e ".[dev]"

# Boot the simulator on its default port (Ctrl-C to stop)
sim:
	python -m sim

# One-time GitHub Copilot login (device flow). Saves an OAuth token to
# .copilot_token.json so the agent can call the Copilot API.
login:
	@python -c "from github_auth import CopilotAuth; a=CopilotAuth(); print(f'Already logged in as {a.username}.') if a.is_logged_in() else a.login()"

# Pre-workshop sanity check. Students run this BEFORE arriving.
verify:
	@python scripts/verify_setup.py

test:
	pytest -q

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache *.egg-info build dist
