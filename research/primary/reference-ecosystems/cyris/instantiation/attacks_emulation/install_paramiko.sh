#!/bin/bash

host_passwd=$1

# check if paramiko has been installed
python3 -c "import paramiko" > /dev/null 2>&1;
if [ $? -eq 1 ]
then
    #echo "* DEBUG: paramiko is not yet installed"
    sudo -S apt-get install python3-paramiko
else
    #echo "* DEBUG: paramiko is already installed"
    :
fi

