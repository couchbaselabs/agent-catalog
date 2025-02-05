cf-pip: init-env install-with-pip post-install
cf-poetry: init-env install-with-poetry post-install

AGENT_CATALOG_LIBS = ../../../libs

init-env:
	@echo "----Creating Conda Environment----"
	conda create -n $(or $(env_name),agentc_env) python=3.12 -y

install-with-poetry:
	@echo "----Installing Requirements----"
	@echo "This may take some time..."
	conda run -n $(or $(env_name),agentc_env) bash -c "\
		poetry install --with analysis && \
		echo '' && \
        echo '----Verifying Installation----' && \
        pip list | grep agentc && \
        echo '' && \
        echo '----agentc Usage----' && \
        agentc --help"

install-with-pip:
	@echo "----Installing Requirements----"
	@echo "This may take some time..."
	conda run -n $(or $(env_name),agentc_env) bash -c "\
		pip install $(AGENT_CATALOG_LIBS)/agentc && \
		pip install $(AGENT_CATALOG_LIBS)/agentc_langchain && \
		pip install -r requirements.txt && \
		echo '' && \
		echo '----Verifying Installation----' && \
		pip list | grep agentc && \
		controlflow version && \
		echo '' && \
		echo '----agentc Usage----' && \
		agentc --help"

post-install:
	@echo "Note: Please run 'conda deactivate', followed by 'conda activate $(or $(env_name),agentc_env)' to activate your python env and run agentc commands"