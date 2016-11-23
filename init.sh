#!/bin/bash

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
