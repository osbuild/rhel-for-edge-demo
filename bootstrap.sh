#!/usr/bin/env bash

USER=$1
PASS=$2

subscription-manager register --username $USER --password $PASS
subscription-manager role --set="Red Hat Enterprise Linux Server"
subscription-manager service-level --set="Self-Support"
subscription-manager usage --set="Development/Test"
subscription-manager attach
yum -y install osbuild-composer composer-cli cockpit-composer bash-completion
systemctl enable --now osbuild-composer.socket
systemctl enable --now cockpit.socket
