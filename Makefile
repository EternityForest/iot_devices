
.PHONY: dev-build-docs
dev-build-docs:
	@sphinx-build -M markdown doc_source doc_build_md
	@rm -rf kaithem/src/docs/api
	@cp -r doc_build_md/markdown/autoapi/iot_devices/ docs/

	@rm -rf doc_build_md

.PHONY: test
test:
	@uv run python -m pytest

.PHONY: test-gpio-e2e
test-gpio-e2e:
	@uv run python scripts/gpio_e2e_test.py