FROM python:alpine
MAINTAINER robin.roth@kit.edu

COPY flit.ini requirements.txt README.rst /hostlist/
COPY hostlist /hostlist/hostlist
COPY tests /hostlist/tests

ENV FLIT_ROOT_INSTALL=1

RUN pip install flit
RUN cd /hostlist && \
    pip install -r requirements.txt && \
    flit install

EXPOSE 80

VOLUME /data
WORKDIR /data

ENTRYPOINT hostlist-daemon
