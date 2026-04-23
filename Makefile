# WifiCities Makefile

REPO_DIR := $(shell pwd)
WC := $(REPO_DIR)/wificities

.PHONY: setup init build flash flash-site serve config validate clean help

help: ## Show this help
	@echo ""
	@echo "  WifiCities — Make targets"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'
	@echo ""

setup: ## Install dependencies and create the wificities command
	./quickstart.sh

init: ## Create a new wificity project (interactive)
	$(WC) init my-wificity

build: ## Build the site for flashing
	cd my-wificity && $(WC) build

flash: ## Flash firmware + site to ESP32
	cd my-wificity && $(WC) flash

flash-site: ## Flash only the site (faster, no firmware)
	cd my-wificity && $(WC) flash --only filesystem

serve: ## Start local dev server with hot reload
	cd my-wificity && $(WC) serve

config: ## Open interactive config menu
	cd my-wificity && $(WC) config

validate: ## Check project for issues
	cd my-wificity && $(WC) validate

clean: ## Remove build artifacts
	rm -rf my-wificity/build
