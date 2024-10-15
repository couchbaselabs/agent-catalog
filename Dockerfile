# TODO (GLENN): This is just a placeholder Dockerfile, we should update this to do more CI/CD stuff.
FROM couchbase
LABEL authors="couchbase"

# Copy all of our packages into the container.
RUN mkdir /opt/agentc
ADD libs /opt/agentc/libs
ADD pyproject.toml /opt/agentc/pyproject.toml

# Download Python 3.12.
RUN apt-get update
RUN mkdir /opt/python3.12
RUN apt-get install -y  \
    wget \
    libffi-dev \
    gcc \
    build-essential \
    curl \
    tcl-dev \
    tk-dev \
    uuid-dev \
    lzma-dev \
    liblzma-dev \
    libssl-dev \
    libsqlite3-dev
RUN wget https://www.python.org/ftp/python/3.12.0/Python-3.12.0.tgz \
    && tar -zxvf Python-3.12.0.tgz \
    && cd Python-3.12.0 \
    && ./configure --enable-optimizations \
    && make altinstall
RUN update-alternatives --install /usr/bin/python python /usr/local/bin/python3.12 1

# Install our packages with Poetry.
WORKDIR /opt/agentc
RUN python -m pip install poetry
RUN poetry install
