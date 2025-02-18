.PHONY: clean

default: setup update activate

pre-setup:
	@./scripts/pre-setup.sh

setup:
	@./scripts/pre-setup.sh
	@./scripts/setup.sh dev

activate:
	@./scripts/activate.sh

update:
	@./scripts/update.sh

docs:
	@./scripts/docs.sh

clean:
	@./scripts/clean.sh
