# ─── PROJ-07 — Mobile Telemetry Boilerplate ───────────────────────
#
# Usage:
#   make up          Start dev environment
#   make prod        Start production environment
#   make test        Run test suite
#   make build       Build Docker image
#   make deploy-sam  Deploy serverless path (SAM)
#   make deploy-tf   Deploy serverless path (Terraform)
#   make clean       Stop containers and remove artifacts
#

SHELL       := /bin/bash
IMAGE_NAME  := proj-07-telemetry
IMAGE_TAG   ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo latest)
DOCKER      := docker
COMPOSE     := docker compose

.PHONY: all up prod build test clean deploy-sam deploy-tf

all: build test

# ─── Build ──────────────────────────────────────────────────────

build:
	$(DOCKER) build -t $(IMAGE_NAME):$(IMAGE_TAG) .
	$(DOCKER) tag $(IMAGE_NAME):$(IMAGE_TAG) $(IMAGE_NAME):latest

# ─── Development ────────────────────────────────────────────────

up:
	$(COMPOSE) -f docker-compose.yml up --build -d

down:
	$(COMPOSE) -f docker-compose.yml down

logs:
	$(COMPOSE) -f docker-compose.yml logs -f

# ─── Production ────────────────────────────────────────────────

prod:
	$(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml up --build -d

# ─── Tests ──────────────────────────────────────────────────────

test:
	python3 -m pytest tests/ -v --tb=short

test-coverage:
	python3 -m pytest tests/ -v --tb=short --cov=app --cov-report=term-missing

# ─── Serverless Deployments ─────────────────────────────────────

deploy-sam:
	@echo "Deploying SAM template..."
	cd infra && sam build --template sam-template.yaml
	cd infra && sam deploy --template-file sam-template.yaml \
		--stack-name proj-07-telemetry \
		--no-execute-changesets

deploy-tf:
	@echo "Deploying Terraform infrastructure..."
	cd infra/terraform && terraform init
	cd infra/terraform && terraform plan -out=tfplan
	cd infra/terraform && terraform apply tfplan

# ─── Docker Push ────────────────────────────────────────────────

push: build
	$(DOCKER) push $(IMAGE_NAME):$(IMAGE_TAG)
	$(DOCKER) push $(IMAGE_NAME):latest

# ─── Clean ──────────────────────────────────────────────────────

clean: down
	$(DOCKER) system prune -f
	rm -f infra/terraform/*.tfstate*
