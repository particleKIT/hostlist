#!/bin/bash

if [[ ! -z $REPOKEY ]]
then
    mkdir ~/.ssh
    echo "$REPOKEY" > ~/.ssh/id_rsa
fi

git clone $REPOURL /data
cd /data
if [[ ! -z $REPODIR ]]
then
    cd $REPODIR
fi

hostlist-daemon
