format:
	python -m ruff format .
	python -m ruff check . --fix

type-check:
	python -m mypy . --ignore-missing-imports

test:
	python -m pytest --cov --cov-fail-under=85