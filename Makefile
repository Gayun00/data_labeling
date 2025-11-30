.PHONY: demo-conversations demo-samples demo-labeler demo-batch demos serve-ui

PYTHON ?= python3

demo-conversations:
	$(PYTHON) scripts/demo_conversation_factory.py

demo-samples:
	$(PYTHON) scripts/demo_sample_ingest.py

demo-labeler:
	$(PYTHON) scripts/demo_labeler.py

demo-batch:
	$(PYTHON) scripts/demo_batch_runner.py

demos: demo-conversations demo-samples demo-labeler

serve-ui:
	$(PYTHON) -m streamlit run ui/app.py
