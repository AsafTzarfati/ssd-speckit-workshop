.PHONY: install sim verify test clean

install:
	pip install -e ".[dev]"

# Boot the simulator on its default port (Ctrl-C to stop)
sim:
	python -m sim

# Pre-workshop sanity check. Students run this BEFORE arriving.
verify:
	@python scripts/verify_setup.py

test:
	pytest -q

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache *.egg-info build dist
