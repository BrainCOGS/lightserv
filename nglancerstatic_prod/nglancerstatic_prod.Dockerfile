FROM ubuntu:xenial-20200212

RUN apt-get update -y && apt-get upgrade -y && \
    apt-get install bash git gcc 'g++' musl-dev curl -y

RUN curl -sL https://deb.nodesource.com/setup_10.x | bash -

# Get node.js
RUN apt install nodejs -y

# clone neuroglacner

ADD https://api.github.com/repos/BrainCOGS/neuroglancer/git/refs/heads/master version.json
RUN git clone -b master https://github.com/BrainCOGS/neuroglancer.git /opt/nglancerstatic

WORKDIR /opt/nglancerstatic

# Install the dependencies required by neuroglancer

RUN npm i

# Run the dev server (--host=0.0.0.0,--port=8081)

CMD npm run dev-server-python