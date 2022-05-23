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

cd /vagrant
composer-cli blueprints push blueprint.toml
echo "Starting compose build"
uuid=$(composer-cli compose start-ostree Edge rhel-edge-commit | awk '{print $2}')

until [ "$(composer-cli compose status | awk '{print $2}')" = "FINISHED" ]; do
   echo "Compose is not ready yet"
   sleep 60
done

echo "Done"