
.DEFAULT_GOAL:=help
SHELL:=/bin/bash
ACTIVATE:=. venv/bin/activate

-include .device.mk
OPENCL_ENV:=PYTHONPATH=main PYTHONPYCACHEPREFIX=caches/pycache PYOPENCL_COMPILER_OUTPUT=1 $(DEVICE_ENV)
#OPENCL_ENV:=PYTHONPATH=main PYTHONPYCACHEPREFIX=caches/pycache $(DEVICE_ENV)

# Create python virtual environment
venv:
	python3 -m venv venv

venv/requirements-updated: venv requirements.txt
	$(ACTIVATE); $(OPENCL_ENV) pip install -Ur requirements.txt
	touch venv/requirements-updated

dependencies: venv/requirements-updated ## Create Python virtual environment and install dependencies

.PHONY: tle-fetch
tle-fetch: ## Fetch TLE records from Celestrak.
	./tle-fetch.sh

.PHONY: run
run: dependencies ## Generate and display skyscape images
	$(ACTIVATE); $(OPENCL_ENV) python main/main.py

.PHONY: test
test: dependencies ## Run tests
	$(ACTIVATE); $(OPENCL_ENV) pytest

.PHONY: test-setup
test-setup: dependencies ## Run test of OpenCL setup.
	$(ACTIVATE); $(OPENCL_ENV) pytest -s test/opencl_setup/test_setup.py

.PHONY: test-sgp4
test-sgp4: dependencies ## Run sgp4 test
	$(ACTIVATE); $(OPENCL_ENV) pytest -s test/celestrak/sgp4/test_sgp4.py

.PHONY: test-jday
test-jday: dependencies ## Run jday test
	$(ACTIVATE); $(OPENCL_ENV) pytest -s test/celestrak/sgp4/test_jday.py

.PHONY: test-astrolib
test-astrolib: dependencies ## Run astrolib test
	$(ACTIVATE); $(OPENCL_ENV) pytest -s test/celestrak/astrolib/test_astrolib.py

.PHONY: test-tle
test-tle: dependencies ## Run tle test
	$(ACTIVATE); $(OPENCL_ENV) pytest -s test/test_tle.py

.PHONY: clinfo
clinfo: ## Run clinfo with OpenCL driver selection
	$(OPENCL_ENV) clinfo --list

.PHONY: clean
clean: ## Remove temporary caches
	rm -rf caches/*

.PHONY: clean-all
clean-all: ## Remove virtual environment, dependencies and temporary caches
	rm -rf venv caches/*

# tput colors
cyan := $(shell tput setaf 6)
reset := $(shell tput sgr0)
#
# Credits for Self documenting Makefile:
# https://www.thapaliya.com/en/writings/well-documented-makefiles/
# https://github.com/awinecki/magicfile/blob/main/Makefile
#
.PHONY: help
help: ## Display this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make $(cyan)[target ...]$(reset)\n\nTargets:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(cyan)%-13s$(reset) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

