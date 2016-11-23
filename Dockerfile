FROM python:alpine
MAINTAINER robin.roth@kit.edu

RUN apk add --no-cache bash git ssh

COPY flit.ini requirements.txt README.rst /hostlist/
COPY hostlist /hostlist/hostlist
COPY tests /hostlist/tests

ENV FLIT_ROOT_INSTALL=1

RUN pip install flit
RUN cd /hostlist && \
    pip install -r requirements.txt && \
    flit install
    
COPY init.sh /

ENV REPOURL=https://github.com/particleKIT/hostlist
ENV REPODIR=tests
ENV REPOKEY=""

EXPOSE 80
WORKDIR /data

ENTRYPOINT /init.sh
