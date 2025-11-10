
.PHONY: dev-build-docs
dev-build-docs:
	@sphinx-build -M markdown doc_source doc_build_md
	@rm -rf kaithem/src/docs/api
	@cp -r doc_build_md/markdown/autoapi/iot_devices/device docs/
	@cp -r doc_build_md/markdown/autoapi/iot_devices/host docs/
	@rm -rf doc_build_md