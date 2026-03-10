PY=python3
PKG=flyin

install:
	$(PY) -m pip install -U pip
	$(PY) -m pip install -e ".[dev]"

run:
	$(PY) -m $(PKG).cli maps/01_maze_nightmare.txt --viz

debug:
	$(PY) -m pdb -m $(PKG).cli maps/01_maze_nightmare.txt --viz

lint:
	python -m flake8 src
	python -m mypy src

clean:
	rm -rf .mypy_cache __pycache__ .pytest_cache *.egg-info dist build