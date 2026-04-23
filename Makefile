.PHONY: install install-dev run test lint format clean

install:
	poetry install

install-dev: install
	poetry run pre-commit install

run:
	cd backend && poetry run python src/main.py

test:
	cd backend && poetry run pytest tests/ -v

lint:
	cd backend && poetry run ruff check src/ tests/
	cd backend && poetry run mypy src/

format:
	cd backend && poetry run ruff format src/ tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.pyc" -delete
