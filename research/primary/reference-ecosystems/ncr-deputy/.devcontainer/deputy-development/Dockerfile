FROM nexus.ocr.cr14.net:8003/rust-development:latest

RUN wget -qO - https://nexus.ocr.cr14.net/repository/ocr-raw-hosted/ubuntu/gpg | apt-key add -
RUN echo 'deb [arch=amd64] https://nexus.ocr.cr14.net/repository/ocr-apt-hosted/ focal main' >> /etc/apt/sources.list.d/ocr.list

RUN apt-get update && apt-get upgrade -y
RUN apt-get install deputy mitmproxy -y

ENV NODE_VERSION=18.20.4
RUN apt-get install -y curl libmariadb-dev-compat libmariadb-dev
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
ENV NVM_DIR=/root/.nvm
RUN . "$NVM_DIR/nvm.sh" && nvm install ${NODE_VERSION}
RUN . "$NVM_DIR/nvm.sh" && nvm use v${NODE_VERSION}
RUN . "$NVM_DIR/nvm.sh" && nvm alias default v${NODE_VERSION}
RUN cp /root/.nvm/versions/node/v${NODE_VERSION}/bin/node /usr/bin/
RUN cp /root/.nvm/versions/node/v${NODE_VERSION}/bin/npm /usr/bin/
RUN /root/.nvm/versions/node/v${NODE_VERSION}/bin/npm install -g yarn
ENV PATH="/root/.nvm/versions/node/v${NODE_VERSION}/bin/:${PATH}"

RUN mkdir -p /home/vscode/.deputy/download
RUN mkdir /home/vscode/.deputy/index
RUN chown -R vscode:vscode /home/vscode/.deputy

COPY ./deputy /usr/bin/deputy
COPY ./deputy-release /usr/bin/deputy-release
COPY ./configuration.toml /home/vscode/.deputy/configuration.toml
