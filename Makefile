PYTHON ?= python

.PHONY: demo test install clean png

demo:            ## Run the collection against the local fixtures
	$(PYTHON) -m collector.run --config stores.yaml

test:            ## Run the test suite
	$(PYTHON) -m pytest

install:         ## Install dependencies
	$(PYTHON) -m pip install -r requirements.txt

png:             ## Re-render sample_output.png from the generated workbook
	$(PYTHON) tools/render_sample_png.py

clean:
	rm -rf output .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
