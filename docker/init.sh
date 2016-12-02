#!/bin/bash

if [[ ! -z $SSLCERT ]]
then
    echo -e "$SSLCERT" > /ssl/cert.pem
fi
if [[ ! -z $SSLPRIVATE ]]
then
    echo -e "$SSLPRIVATE" > /ssl/privkey.pem
fi
if [[ ! -z $SSLCHAIN ]]
then
    echo -e "$SSLCHAIN" > /ssl/certchain.pem
fi

if [[ ! -z $REPOSSHKEY ]]
then
    mkdir -p ~/.ssh
    echo -e "$REPOSSHKEY" > ~/.ssh/id_rsa
    chmod 600 ~/.ssh/id_rsa
fi

if [[ ! -z $REPOHOSTKEY ]]
then
    mkdir -p ~/.ssh
    echo "$REPOHOSTKEY" > ~/.ssh/known_hosts
fi

git clone $REPOURL /data
cd /data
if [[ ! -z $REPODIR ]]
then
    cd $REPODIR
fi

hostlist-daemon
