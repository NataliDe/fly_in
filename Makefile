PYTHON=python3

install:
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(PYTHON) -m fly_in.main maps/easy/01_linear_path.txt --auto --log

debug:
	$(PYTHON) -m pdb -m fly_in.main maps/easy/01_linear_path.txt

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .mypy_cache -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +

lint:
	flake8 .
	mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict:
	flake8 .
	mypy . --strict
