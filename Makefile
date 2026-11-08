
.PHONY: dev-build-docs
dev-build-docs:
	@sphinx-build -M markdown doc_source doc_build_md
	@rm -rf kaithem/src/docs/api
	@cp -r doc_build_md/markdown/autoapi/iot_devices/ docs/

	@rm -rf doc_build_md

.PHONY: test
test:
	@uv run python -m pytest tests/
	@uv run python scripts/gpio_e2e_test.py
	@uv run python scripts/matter_e2e_test.py