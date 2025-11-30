.PHONY: demo-conversations demo-samples demo-labeler demos

PYTHON ?= python3

demo-conversations:
	$(PYTHON) scripts/demo_conversation_factory.py

demo-samples:
	$(PYTHON) scripts/demo_sample_ingest.py

demo-labeler:
	$(PYTHON) scripts/demo_labeler.py

demos: demo-conversations demo-samples demo-labeler
