.PHONY: clean

# Modify the path to the scripts directory as needed.
SCRIPTS_DIRECTORY = ../../../../scripts

default: setup update activate

pre-setup:
	@$(SCRIPTS_DIRECTORY)/pre-setup.sh

setup:
	@$(SCRIPTS_DIRECTORY)/pre-setup.sh
	@$(SCRIPTS_DIRECTORY)/setup.sh user

activate:
	@$(SCRIPTS_DIRECTORY)/activate.sh

update:
	@$(SCRIPTS_DIRECTORY)/update.sh

clean:
	@$(SCRIPTS_DIRECTORY)/clean.sh
