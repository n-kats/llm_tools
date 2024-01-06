target = utils llm_tools llm_clis syllabus

.PHONY: lint
lint:
	poetry run ruff check ${target}
	poetry run mypy ${target}

.PHONY: format
format:
	poetry run ruff format ${target}
	poetry run ruff check --fix ${target}
