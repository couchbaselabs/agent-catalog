.PHONY: clean

# Modify the path to the scripts directory as needed.
SCRIPTS_DIRECTORY = ./scripts

default: setup update activate

check:
	@$(SCRIPTS_DIRECTORY)/pre-setup.sh

setup:
	@$(SCRIPTS_DIRECTORY)/pre-setup.sh
	@$(SCRIPTS_DIRECTORY)/setup.sh dev

activate:
	@$(SCRIPTS_DIRECTORY)/activate.sh

update:
	@$(SCRIPTS_DIRECTORY)/update.sh

docs:
	@$(SCRIPTS_DIRECTORY)/docs.sh

clean:
	@$(SCRIPTS_DIRECTORY)/clean.sh
