FROM ubuntu:xenial-20200212

RUN apt-get update -y && apt-get upgrade -y && \
    apt-get install bash git gcc 'g++' musl-dev curl -y

RUN curl -sL https://deb.nodesource.com/setup_10.x | bash -

# Get node.js
RUN apt install nodejs -y

# clone neuroglacner

WORKDIR /opt

RUN git clone https://github.com/BrainCOGS/neuroglancer.git nglancerstatic

WORKDIR /opt/nglancerstatic

# Install the dependencies required by neuroglancer

RUN npm i

# Run the dev server (--host=0.0.0.0,--port=8081)

CMD npm run dev-server-python