test:
	python -m unittest discover -s tests -v

install:
	pip install -e ".[tools]"

ui:
	@echo "Open http://localhost:8000/ui/scoreboard.html"
	python -m http.server 8000

.PHONY: test install ui
