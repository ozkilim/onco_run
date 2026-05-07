# Convenience entrypoints. All commands assume Docker is on PATH.

SHELL := /bin/bash
TAG ?= onco-run:latest
RECIPE ?= recipes/example.yaml
WEIGHTS_DIR ?= models
PREDICTORS_DIR ?= predictors
SLIDES_DIR ?= ./slides
OUTPUT_DIR ?= ./output

.PHONY: help
help:
	@echo "Targets:"
	@echo "  build           Build CUDA image as $(TAG)"
	@echo "  build-cpu       Build CPU-only image as $(TAG)"
	@echo "  bake            Build image with RECIPE+WEIGHTS_DIR baked in"
	@echo "                    make bake RECIPE=recipes/lung.yaml WEIGHTS_DIR=models TAG=onco-run:lung_v1"
	@echo "  run             Run inference (uses local SLIDES_DIR / OUTPUT_DIR)"
	@echo "  run-cpu         Same, force CPU"
	@echo "  package         Save image to a sendable folder under dist/"
	@echo "                    make package TAG=onco-run:lung_v1"
	@echo "  shell           Drop into a shell inside the image"
	@echo "  test            Run the test suite (host-side, requires deps installed)"

.PHONY: build
build:
	./scripts/build.sh --tag $(TAG)

.PHONY: build-cpu
build-cpu:
	./scripts/build.sh --cpu --tag $(TAG)

.PHONY: bake
bake:
	./scripts/build_with_recipe.sh \
		--recipe $(RECIPE) \
		--weights $(WEIGHTS_DIR) \
		--predictors $(PREDICTORS_DIR) \
		--tag $(TAG)

.PHONY: run
run:
	mkdir -p $(OUTPUT_DIR)
	docker run --rm --gpus all \
		-v "$(abspath $(SLIDES_DIR))":/data/slides:ro \
		-v "$(abspath $(OUTPUT_DIR))":/data/output \
		-v "$(abspath $(RECIPE))":/app/recipes/recipe.yaml:ro \
		-v "$(abspath $(WEIGHTS_DIR))":/app/models:ro \
		-v "$(abspath $(PREDICTORS_DIR))":/app/predictors:ro \
		$(TAG)

.PHONY: run-cpu
run-cpu:
	mkdir -p $(OUTPUT_DIR)
	docker run --rm \
		-v "$(abspath $(SLIDES_DIR))":/data/slides:ro \
		-v "$(abspath $(OUTPUT_DIR))":/data/output \
		-v "$(abspath $(RECIPE))":/app/recipes/recipe.yaml:ro \
		-v "$(abspath $(WEIGHTS_DIR))":/app/models:ro \
		-v "$(abspath $(PREDICTORS_DIR))":/app/predictors:ro \
		$(TAG)

.PHONY: package
package:
	./scripts/package.sh --tag $(TAG)

.PHONY: shell
shell:
	docker run --rm -it --entrypoint bash $(TAG)

.PHONY: test
test:
	pytest -q tests
