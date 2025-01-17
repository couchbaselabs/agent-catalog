dev-local: init-env install-agentc-pip post-install

# To install agentc in any project, given that the clone
# of agent-catalog and project directory have common parent
AGENT_CATALOG_LIBS = ../agent-catalog/libs

init-env:
	@echo "----Creating Conda Environment----"
	conda create -n agentc_env python=3.12 -y

install-agentc-pip:
	@echo "----Installing Agentc----"
	@echo "This may take some time..."
	conda run -n agentc_env bash -c "\
		pip install $(AGENT_CATALOG_LIBS)/agentc && \
		pip install $(AGENT_CATALOG_LIBS)/agentc_langchain && \
		echo '' && \
		echo '----Verifying Installation----' && \
		pip list | grep agentc && \
		echo '' && \
		echo '----agentc Usage----' && \
		agentc --help"

post-install:
	@echo "Note: Please run 'conda agentc_env activate' to activate your python env and run agentc commands"