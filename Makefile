.PHONY: build deploy api cli health diagnose fix suggest fix-dry-run validate

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

suggest:
	python k8s-diagnostics-cli.py suggest

fix-dry-run:
	python k8s-diagnostics-cli.py fix --dry-run

fix:
	python k8s-diagnostics-cli.py fix

cleanup:
	python k8s-diagnostics-cli.py cleanup

validate:
	./scripts/validate-repo.sh

# API calls (programmatic)
api-health:
	curl -s http://localhost:8000/health | jq

api-diagnose:
	curl -s http://localhost:8000/diagnose/pod/$(NS)/$(POD) | jq

api-network:
	curl -s http://localhost:8000/diagnose/network | jq

api-fix:
	curl -s -H "X-API-Key: $(K8S_DIAGNOSTICS_API_KEY)" -X POST http://localhost:8000/fix/restart-failed-pods | jq

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

chaos:
	@echo "Setting up chaos sandbox..."
	@bash scripts/chaos.sh
