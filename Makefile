.PHONY: build deploy api cli health diagnose fix

# Build and deployment
build:
	docker build -t k8s-diagnostics:latest -f docker/Dockerfile .

deploy:
	kubectl apply -f k8s/deployment.yaml

# API operations
api:
	python -m src.k8s_diagnostics.api.server

# CLI operations
health:
	python k8s-diagnostics-cli.py health

diagnose:
	python k8s-diagnostics-cli.py diagnose $(NS) $(POD)

network:
	python k8s-diagnostics-cli.py network

detect:
	python k8s-diagnostics-cli.py detect

fix:
	python k8s-diagnostics-cli.py fix

cleanup:
	python k8s-diagnostics-cli.py cleanup

# API calls (programmatic)
api-health:
	curl -s http://localhost:8000/health | jq

api-diagnose:
	curl -s http://localhost:8000/diagnose/pod/$(NS)/$(POD) | jq

api-network:
	curl -s http://localhost:8000/diagnose/network | jq

api-fix:
	curl -s -X POST http://localhost:8000/fix/restart-failed-pods | jq

# Setup
install:
	pip install -r requirements.txt

# Examples
example-health:
	@echo "Getting cluster health..."
	@python k8s-diagnostics-cli.py health

example-detect:
	@echo "Detecting issues..."
	@python k8s-diagnostics-cli.py detect