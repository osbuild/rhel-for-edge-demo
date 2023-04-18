lang en_US.UTF-8
keyboard us
timezone UTC
zerombr
clearpart --all --initlabel
autopart --type=plain --fstype=xfs --nohome
reboot
text
network --bootproto=dhcp
user --name=core --groups=wheel --password=edge

ostreesetup --nogpg --url=http://10.0.2.2:8000/repo/ --osname=rhel --remote=edge --ref=rhel/9/x86_64/edge
#ostreesetup --nogpg --url=http://10.0.2.2:8000/repo/ --osname=rhel --remote=edge --ref=rhel/8/x86_64/edge
%post

#stage updates as they become available. This is highly recommended
echo AutomaticUpdatePolicy=stage >> /etc/rpm-ostreed.conf

#This is a simple example that will look for staged rpm-ostree updates and apply them per the timer if they exist
cat > /etc/systemd/system/applyupdate.service << 'EOF'
[Unit]
Description=Apply Update Check

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'if [[ $(rpm-ostree status -v | grep "Staged: yes") ]]; then systemctl --message="Applying OTA update" reboot; else logger "Running latest available update"; fi'
EOF

cat > /etc/systemd/system/applyupdate.timer << EOF
[Unit]
Description=Daily Update Reboot Check.

[Timer]
#Nightly example maintenance window
OnCalendar=*-*-* 01:30:00
#weekly example for Sunday at midnight
#OnCalendar=Sun *-*-* 00:00:00

[Install]
WantedBy=multi-user.target
EOF

systemctl enable podman-auto-update.timer rpm-ostreed-automatic.timer applyupdate.timer
%end

%post
#create a unit file to run our example workload 
cat > /etc/container/systemd/boinc.container <<EOF
[Service]
Restart=always
ExecStartPre=-/bin/mkdir -p /opt/appdata/boinc/slots
ExecStartPre=-/bin/mkdir -p /opt/appdata/boinc/locale

[Container]
ContainerName=boinc
Image=docker.io/boinc/client:latest
Label="io.containers.autoupdate=image"
Network=host
PublishPort=31416:31416
Timezone=local
Volume=/opt/appdata/boinc:/var/lib/boinc:Z

[Install]
WantedBy=default.target
EOF
%end

