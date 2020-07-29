# RHEL for Edge with Image Builder Demo

## Requirements

[RHEL 8.3 Beta](https://access.redhat.com/products/red-hat-enterprise-linux/beta)

Name            | Filename
----------------|---------------------------------
Boot ISO        | rhel-8.3-beta-1-x86_64-boot.iso
KVM Guest Image | rhel-8.3-beta-1-x86_64-kvm.qcow2


## Install Image Builder

### Run RHEL beta via VM script

```
vm --persist rhel-8.3-beta-1-x86_64-kvm.qcow2
```

### Register the system

```
subscription-manager register --username <redhat_login_username> --password <redhat_login_password>
subscription-manager role --set="Red Hat Enterprise Linux Server"
subscription-manager service-level --set="Self-Support"
subscription-manager usage --set="Development/Test"
subscription-manager attach
```

### Install Image Builder
```
yum install osbuild-composer cockpit-composer
```

### Enable web console
```
systemctl enable --now cockpit.socket
```

## Build a RHEL for Edge commit

URL to connect to is: http://localhost:9091

 1. Create a Blueprint ![screenshot](screenshots/blueprint.png)
 2. Add packages (optionally) ![screenshot](screenshots/packages.png)
 3. Create Image ![screenshot](screenshots/create.png)
 4. Wait
 5. Tarball with the commit is ready to download ![screenshot](screenshots/download.png)

## Inspect the commit

Extract the downloaded tarball via `tar xvf <uuid>-commit.tar`. It should
contain a `compose.json` and a `repo` directory. The former contains the
metadata about the commit, like the "Ref" (`ref`) and the commit id
(`ostree-commit`). The `repo` folder is a OSTree repository that contains
the commit.
The `ostree` and `rpm-ostree` commands can be used to inspect the contents:
The list of rpm packages included in the commit can be listed via
```
# print a list of packages in the commit
rpm-ostree db list rhel/8/x86_64/edge --repo=repo
```

## Install the commit

### Setup a webserver

```
podman build -t httpd .
podman run --rm -p 8000:80 -v $(pwd):/var/www/html:Z httpd
```

### Install to a disk via Anaconda

The installer, anaconda, on the `boot.iso` installation medium is can
be used to install the commit. To configure the installer to use the
newly build commit, a "kickstart" configuration [`edge.ks`](edge.ks),
is used. It is setup for non-interactive, text-based installation.
The important line within the kickstart is the `ostreesetup` directive
which instructs the installer to fetch and deploy the commit.
Additionally a user `core` (pw: `edge`) is created.

For demonstration purposes we create an empty `qcow2` with a size of
`5G`, to act as the installation target:

```
qemu-img create -f qcow2 disk.qcow2 5G
```

The installer is run with qemu:
```
qemu-system-x86_64 \
  -m 2048 \
  -enable-kvm \
  -device virtio-net-pci,netdev=n0 \
  -netdev user,id=n0,net=10.0.2.0/24 \
  -drive file=disk.qcow2 \
  -cdrom rhel-8.3-beta-1-x86_64-boot.iso
```

To use the prepared kicksstart file, instead of the default one of
the `boot.iso`, an additional kernel parameter is needed (hit `TAB`
on the `Install ...` entry):

```
inst.ks=http://10.0.2.2:8000/edge.ks
```

![screenshot](screenshots/install.png)
