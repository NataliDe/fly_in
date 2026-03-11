PYTHON=python3
PIP=pip3
MAP=maps/01_linear_path.txt

install:
	$(PIP) install -r requirements.txt

run:
	$(PYTHON) -m fly_in.main $(MAP)

debug:
	$(PYTHON) -m pdb -m fly_in.main $(MAP)

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -prune -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +

lint:
	flake8 .
	mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs
