.PHONY: demo-conversations demo-samples demos

PYTHON ?= python3

demo-conversations:
	$(PYTHON) scripts/demo_conversation_factory.py

demo-samples:
	$(PYTHON) scripts/demo_sample_ingest.py

demos: demo-conversations demo-samples
