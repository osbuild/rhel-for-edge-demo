# Building RHEL for Edge with Image Builder

This demonstrates the use of [Image Builder](https://www.osbuild.org/) to
create a (custom) RHEL for Edge [OSTree](https://ostree.readthedocs.io/en/latest/)
commit and how to install those to a disk or a virtual machine image.

The latest version of Image Builder can create several types of RHEL for Edge artifacts, all of these are essentially a delivery mechanism for the OSTree commit. Think of this as the OS image, as it literally contains the entire operating system. This demo will show how to create the initial OSTree commit, make it available via HTTP/HTTPS, walkthrough several install paths, install a system, and create updates.

```
                      ┌─────────────────┐
                      │                 │
                      │  Image Builder  │
                      │                 │
                      └────────┬────────┘
                               │
                               ▼
                       ┌───────────────┐
                       │               │
                       │ OSTree Commit │
                       │               │
                       └───────┬───────┘
                               │
             ┌─────────────────┼──────────────────┐
             │                 │                  │
     ┌───────▼───────┐  ┌──────▼──────┐   ┌───────▼───────┐
     │               │  │             │   │               │
     │ OCI Container │  │  Installer  │   │  Raw OSTree   │
     │     (tar)     │  │    (iso)    │   │     (tar)     │
     └───────────────┘  └─────────────┘   └───────────────┘
```

## Requirements

Install Image Builder on the latest release of [RHEL](https://developers.redhat.com/products/rhel/download).
8.3 is the minimal required version, but this demo will include features from
later releases. We recommend using RHEL 9.2 or later. The *KVM Guest Image* is used to install Image Builder and build a
RHEL for Edge commit. The *Boot ISO* is then used to install that commit. 

Name            | Filename
----------------|-------------------------
Boot ISO        | rhel-baseos-9.x-x86_64-boot.iso
KVM Guest Image | rhel-baseos-9.x-x86_64-kvm.qcow2


## Install Image Builder

### Run RHEL inside a virtual machine

A small helper script is used to start the RHEL 9.x Guest Image. It uses
[cloud-init](https://cloudinit.readthedocs.io/en/latest/) to provision a
`root` user (password `r`). The script also enables port forwarding for
the ssh and web console ports (`22` → `2222` (host) and
`9090` → `9091`).

```
vm --persist rhel-baseos-9.x-x86_64-kvm.qcow2
```

### Register the system

To be able to install packages the VM must be registered via:

```
subscription-manager register --username <redhat_login_username> --password <redhat_login_password>
subscription-manager role --set="Red Hat Enterprise Linux Server"
subscription-manager service-level --set="Self-Support"
subscription-manager usage --set="Development/Test"
subscription-manager attach
```

### Install Image Builder

Image Builder consists of different components: `osbuild-composer` is the
service that sits between the low level `osbuild` tool and various front
ends, such as `cockpit-composer` (web) and `composer-cli` (command line).
It provides an API that is used front-ends, does job queue management, and
internally calls out to one or more worker services which in turn then use
`osbuild` to actually assemble the operating system artifacts such as
virtual machine images or in the case of RHEL for Edge OSTree commits.

All necessary components are now included in RHEL 8.3+, and can easily be
installed via:

```
yum install -y osbuild-composer cockpit-composer
```

The `osbuild-compser` service needs to be explicitly enabled:

```
sudo systemctl enable --now osbuild-composer.socket
```

NB: Technically only the socket, i.e. the API endpoint is enabled here, not
the service itself. The services will be started on-demand as soon as the
first client connects.

### Enable web console
The Image Builder front end is a plugin to the web console (*cockpit*),
which needs to be enabled.

```
systemctl enable --now cockpit.socket
```

## Build a RHEL for Edge container

Navigate to the web console via a browser on the host. URL: http://localhost:9091
There, *Image Builder* is found under *Apps* in the right menu.
Images, or in our case, commits, are generated from so called *Blueprints*,
which are customizations that are applied to existing *Image Types*,
e.g. "RHEL for Edge Container". Internally there is a queue that will
distribute compose requests to workers, which in turn are building the
commits / images. The UI flow is as follows:

 1. Create a Blueprint ![screenshot](screenshots/blueprint.png)
 2. Customization: add packages ![screenshot](screenshots/packages.png)
 3. Create the Image (RHEL for Edge Container) ![screenshot](screenshots/create.png)
 4. Wait for the build to finish ![screenshot](screenshots/building.png)
 5. Tarball with the commit is ready to download ![screenshot](screenshots/download.png)

### Build via the command line

Commits can also build from the command line, via the help of
the `composer-cli` tool (`yum install composer-cli`).

A new blueprint is created from a TOML file, e.g. [`blueprint.toml`](blueprint.toml):

```
$> composer-cli blueprints push blueprint.toml
```

From this a compose is created for the previously created blueprint
(`Edge`). The type of the compose here is `rhel-edge-container`. The
UUID if the compose can later be used to obtain the artifact.

```
$> composer-cli compose start-ostree Edge rhel-edge-container
Compose <uuid> added to the queue
```

The status of a compose can be inspected via:

```
$> composer-cli compose status
<uuid> RUNNING  Thu Jul 30 09:36:14 2020 Edge            0.0.1 rhel-edge-container
```

Finally the container can be downloaded via
```
$> composer-cli compose image <uuid>
<uuid>-container.tar: 778.73 MB
```

<details>
  <summary>Click to see how to inspect OSTree Commits</summary>
  
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
rpm-ostree db list rhel/9/x86_64/edge --repo=repo
```
</details>

## Install RHEL for Edge 

### Run the Container to serve the Image

In order to fetch the commit from the (generic) installer, it needs to be
served via HTTP. The container that was just created runs nginx and will serve the OSTree commit.

Import & tag the container
```
$> skopeo copy oci-archive:<UUID>-container.tar containers-storage:localhost/rfe-mirror:latest
```
Run the container. Tip! We can also mount other files we want to serve via the same container. This example is going to serve a kickstart file and the same thing will work with ignition configs.
```
$> podman run --rm -p 8000:8080 -v ./edge.ks:/var/www/html/edge.ks:z rfe-mirror
```

The repo will now be available at http://10.0.2.2:8000/repo and the supplied kickstart at http://10.0.2.2:8000/edge.ks
Note, that we've switched the default 8080 port to 8000 on the host so we don't collide with the optional FDO components described later on. If you're not using FDO, then sticking with port 8080 is a great choice.

### Network Install using Anaconda
<details>
  <summary>Click to view the Network Install</summary>
  
  ### Install to a disk via Anaconda (Basic Example)
  
  The installer, anaconda, on the `boot.iso` installation medium can
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
  -cdrom rhel-8.4-x86_64-boot.iso
```

To use the prepared kickstart file, instead of the default one of
the `boot.iso`, an additional kernel parameter is needed (hit `TAB`
on the `Install Red Hat Enterprise Linux 8.3` entry):

```
inst.ks=http://10.0.2.2:8000/edge.ks
```

![screenshot](screenshots/install.png)

As an alternative to supplying the kickstart location via the kernel
command line, the `mkksiso` (`lorax` package) can be used to inject
the kickstart file into the boot iso:

```
mkksiso edge.ks rhel-baseos-8.x-x86_64-boot.iso boot.iso
```
</details>

### Create an installer image for disconnected environments
<details>
  <summary>Click to create an installer</summary>
  
  Image Builder can create installer media that embeds the OSTree commit. This is perfect for disconnected environments that require an ISO, thumb drive, or some form of media that doesn't depend on network access.
  

#### Build via the command line

An empty blueprint is required to create an installer. An example TOML file is included in this repo, e.g. installer.toml:

```
$> composer-cli blueprints push installer.toml
```

Next, start a `rhel-edge-installer` compose for the blueprint created in the previous step. Passing the --url to the OSTree repository of the commit to embed in the image.
```
$> composer-cli compose start-ostree RFE-Installer rhel-edge-installer --url http://10.0.2.2:8000/repo/ 
Compose c5c160a4-8f41-43d0-b842-495e24826b1a added to the queue
```

When the compose is complete download the ISO

```
$> composer-cli compose image <uuid>
<uuid>-rhel-boot.iso: 1646.39 MB
```

The installer image can be written to optical or flash media using standard methods. A streamlined UI is provided for network & storage configuration and a kickstart can be injected for further customizations and fully automated installs. 

The same workflow is available in the web UI as well:
![screenshot](screenshots/installer.png)

</details>

### Create an installer image for use with FIDO Device Onboarding (FDO) - New w/ 8.6 & 9.0 (Tech Preview)
<details>
  <summary>Click to create an Simplified Installer Image w/ FDO</summary>
  
  FDO is a great technology that aims to automate & secure device onboarding in Edge environments. If you're not familiar with the technology [this video](https://www.youtube.com/watch?v=_nq5IAVbl2Y) is a good intro. FDO is currently only available via the Simplified Installer. This installation path uses coreos-install to write the OStree commit straight to disk. This means there's no need to embed a kickstart config, and any customization can be applied via FDO or any external management tool like Ansible. This is a perfect way to flash systems, ship them, verify the device's integrity, onboard once they're deployed in the field, and then pass any sensative data over the secure FDO channel. coreos-install can deploy from an ISO, USB, or via a network install. Please note that only UEFI firmware is supported.
  

#### Build via the command line

A blueprint with 1) an empty packages section 2) a few additional options is required to create a simplified-installer image. An example TOML file is included in this repo, e.g. simplified-installer.toml (feel free to adjust this as needed for your environment):

```
$> composer-cli blueprints push simplified-installer.toml
```

Next, start a `edge-simplified-installer` compose for the blueprint created in the previous step. Passing the --url to the OSTree repository of the commit to embed in the image.
```
$> composer-cli compose start-ostree simplified-installer edge-simplified-installer --url http://10.0.2.2:8000/repo/ 
Compose 96fc0e4e-ad76-4cbd-b875-91e69a1d7efc added to the queue
```

When the compose is complete download the ISO

```
$> composer-cli compose image <uuid>
<uuid>-simplified-installer.iso: 841M MB
```

The installer image can be written to optical or flash media using standard methods. To use with a network install (PXE, iPXE, or http boot) simply copy the contents of the image to a http or tftp endpoint and edit /EFI/Boot/grub.cfg for your environment. 

  It may be necessary to adjust the path to the vmlinuz & initrd.img as well as configure coreos.inst.image_url= as illustrated below.

Original:
```
  linux /images/pxeboot/vmlinuz rd.neednet=1 coreos.inst.crypt_root=1 coreos.inst.isoroot=RHEL-9-0-0-BaseOS-x86_64 coreos.inst.install_dev=/dev/vda coreos.inst.image_file=/run/media/iso/disk.img.xz coreos.inst.insecure fdo.manufacturing_server_url=http://10.0.0.2:8080 fdo.diun_pub_key_insecure=true quiet
        initrd /images/pxeboot/initrd.img
```
Edited:
```
  linux /si/images/pxeboot/vmlinuz rd.neednet=1 coreos.inst.crypt_root=1 coreos.inst.install_dev=/dev/vda coreos.inst.image_url=http://10.0.0.2/si/disk.img.xz coreos.inst.insecure fdo.manufacturing_server_url=http://10.0.0.2:8080 fdo.diun_pub_key_insecure=true console=tty0 console=ttyS0,115200 quiet
        initrd /si/images/pxeboot/initrd.img
```

Before installing and provisioning the system, we need to configure FDO. Production environment will likely want to spread out the different services in a proper micro-service fashion. For the scope of this example we'll be using the FDO all-in-one deployment. Run the following commands on the image builder system:
```
$> yum -y install fdo-admin-cli && systemctl enable --now fdo-aio
```
This will generate all the necessary configs and keys needed for FDO to work. This repo provides an alternate serviceinfo_api_server.yml file as an example to recreate the same demo as edge2.ks. To use file simply add the desired ssh key and add replace the service_info_auth_token & admin_auth_token from the serviceinfo_api_server.yml file that was generated on your system. Next, copy this file to /etc/fdo/aio/configs/, copy & extract device0.tgz under /etc/, and run `systemctl restart fdo-aio` for the changes to take effect. This assumes that you are provisioning a VM using UEFI w/ a TPM configured. Adjust /dev/vda as necessary to use with other environments. 
  
  
</details>

### Using Ignition to apply configuration with the Simplified Installer
<details>
  <summary>Click to learn more about using Ignition to provide configuration </summary>

Ignition is very similar to Cloud-Init and well supported with both rpm-ostree and the coreos-installer, both of which are used when a Simplified Installer image is created. We've converted the edge2.ks example into Ingition to serve as an example. Ingnition is intended to be machine generated & machine read. Our example will start with human readable/editable configs and converted using butane to render them for final use with the image. To embed the config in Image Builder's blueprint we will encode the file using base64. It may seem convoluded to go through this process, but it's super simple to automate and will make long-term maintenance easier for developers/admins. 

One other thing worth noting is Ignition is capable of fetching remote configs. This is incredibly powerful if you control DNS and want systems in different zones to have different configs. It's also really helpful for iterating on the config as changes to the file won't require building a new installation image to embed the changes. We recommend embedding a stub config in your image that configures a user & ssh key and fetching the remaining options from a web server for doing development. While this same approach is perfectly fine for some production environments, others will benefit from embedding the complete config in the image. We are providing a complete example config as well called full.bu. 

The process 

#### Editing and rendering Ignition config

These steps can be run from the system that has Image Builder installed on it. Begin by editing the stub.bu config in this repo. Add your ssh key and web server that is hosting the remote configuration that we will render. The password hash continues to use the same demo password of "edge" (please change this before using in production). If you prefer to use a complete config instead of the stub, replace full.bu in place of stub.bu in the steps below.

Once the file has been updated, we'll use butane to render the json config for Ignition.

```
$> podman run -i --rm quay.io/coreos/butane:release \
       --pretty --strict < stub.bu > stub.ign
```

Next, let's render the remote side of the config.
```
$> run -i --rm quay.io/coreos/butane:release \
       --pretty --strict < remote.bu > remote.ign
```

Next, convert the config to base64. This is the form we need to insert into the blueprint.
```
$> cat stub.ign| base64 > stub.ign.b64
```

At this point, we will edit the simplified-installer-ign.toml blueprint and paste the contents of stub.ign.b64 inside the triple quotes of this section:

```
[customizations.ignition.embedded]
config = """
```

Now we're ready to generate the installer image. Start a `edge-simplified-installer` compose for the blueprint created in the previous step. Passing the --url to the OSTree repository of the commit to embed in the image.
```
$> composer-cli compose start-ostree simplified-installer-ign edge-simplified-installer --url http://10.0.2.2:8000/repo/
Compose 51et1e4e-ad76-4cbd-b875-94c69a9d4dxq added to the queue
```

When the compose is complete download, boot the ISO, and be amazed! It's worth noting that Ignition can be used with or without FDO, and this is incredibly flexible and powerful capabilities. While there are overlapping capabilities with Ignition & FDO, and we recommend using choosing a path that makes sense for your environment. 

</details>

## Create Image Updates

Updates are delivered in form of new commits. This provides one
of the most important features of OSTree: atomic and safe updates.
This means that an update of the system to a new commit will be
deployed either fully or not at all, even if the update process
gets interrupted. Additionally, the old state of the system, i.e.
the deployment of the old commit, is kept around. In case the new
update does not work as expected, it is easy to go back to the
old commit.

Creating a new update commit, which can include new versions of
packages or additional packages, is the same as creating a new
"image", in Image Builder terms, but with the commit id of the
current deployment (or commit) as the *parent*. On a booted system
the commit id can be found via `rpm-ostree status` and can optionally be passed to Image Builder via the Web UI or CLI. An easier option is to supply the `Repository URL` and let Image Builder fetch the commit id on your behalf.  

![screenshot](screenshots/updates2.png)

After the new commit is built, it needs to be served via http,
very much like the initial commit above. Then the system can
be updated via

```
rpm-ostree update
```

This will create a new deployment of the new commit. A reboot, via
`systemctl reboot`, is all that is necessary to boot into that
new deployment.
If something in the new deployment is not as it should be, the old
deployment can be restored via `rpm-ostree rollback`.

## RHEL for Edge Client Configuration Examples

The second kickstart example, [`edge2.ks`](edge2.ks), will install the
 same ostree commit as well as demonstrate the use of a few features in 
`%post` that makes the OS much easier to manage when using a large 
fleet of systems. To use this example simply adjust the kickstart 
being used:
```
inst.ks=http://10.0.2.2:8000/edge2.ks
```

###New in 9.2+ Using Image Builder's Expanded Blueprint Customizations
We've converted all of the examples from [`edge2.ks`](edge2.ks) and an ostree commit (edge-container) generated using edge_demo.toml will contain all of these configurations. Often for more "enterprisy" environments it can be advantageous to separate OS & application configuration from the image. Environments like this typically benefit greatly from tools like ansible, puppet, etc. However, a lot of edge systems follow a pattern more similar to embedded devices where the image needs to be 100% preconfigured. This example blueprint will help guide you to create an OS image that is ready to run with any needed OS customizations, one of more traditional or containerized applications, and this can be installed using any of the methods described above (anaconda/kickstart, simplified-installer, etc).  

### Nodes will automatically stage ostree updates
As new OStree commits are created via Image Builder and made 
avaialable, clients will stage the updates locally. Enable staging 
by setting `AutomaticUpdatePolicy=stage` in `/etc/rpm-ostreed.conf`.
 The `rpm-ostreed-automatic.timer` will also need to be enabled as
 shown in the example.

### Manage containers as a system service
Containers are an ideal vehicle to help minimize "patch Tuesday" 
style problems, thus making the this means of application 
packaging perfect for long life devices deployed outside of 
traditional data centers. Podman natively supports systemd as a 
manager and this results in one of the lightest weight solutions 
for running containers. This demo originally showed an example boinc container 
systemd unit file generated by `podman generate systemd`. systemd 
will ensure the `container-boinc.service` is running at startup 
and in the case that it fails at runtime, automatically restarted 
via `Restart=always`. With the release of RHEL 9.2, Podman now include support
for Quadlet. We have updated the examples in the repo to use Quadlet rather than
generating unit files. The end result is the same, but Quadlet is the prefered mechanism moving foward.
This same concept extends to multiple containers and/or pods and these configs can easily be included in 
images or managed independently via Ansible (or similar tools).

### Automatically update Containers
Podman has recently implemented the ability to automatically update 
containers. The example includes the label 
`io.containers.autoupdate=image` to notify Podman that it should be 
running the latest image with the defined tag. systemd timers are 
included to schedule this operation.

### systemd timers are used for local actions and maintenance windows
Timers are very similar to chron jobs, but also offer some amazing 
features that benefit this use case. Essentially they're managed like 
any other systemd unit file and the details for options can be found 
[here.](https://www.freedesktop.org/software/systemd/man/systemd.timer.html) 
```
$ systemctl list-timers
NEXT                         LEFT     LAST                         PASSED       UNIT                         ACTIVATES
Thu 2020-09-03 00:42:57 UTC  21h left Wed 2020-09-02 00:08:54 UTC  3h 30min ago podman-auto-update.timer     podman-auto-update.service
Thu 2020-09-03 01:30:00 UTC  21h left n/a                          n/a          applyupdate.timer            applyupdate.service
Thu 2020-09-03 03:00:07 UTC  23h left Wed 2020-09-02 03:00:07 UTC  39min ago    rpm-ostreed-automatic.timer  rpm-ostreed-automatic.service
```

#### Splaying events
Some actions like downloading an OS update or a container image should 
ideally use some type of *splay* to ensure that a reasonable load is 
placed on the registry and ostree mirror. Using RandomizedDelaySec=86400 
will randomize the timer across a 24 hour period. This is a highly 
effect approach for events that are not time sensative and when it 
is desireable to spread the load to conserve backend resources.

#### When not to splay
For events like applying OS updates, it's best to carefully target a 
maintenance window to ensure the SLA is met and the downtime is very 
minimal and predictible. The provided example will apply updates 
nighly at 1:30 UTC (OnCalendar=*-*-* 01:30:00). A more realistic example 
might follow a weekly maintenance window on Sunday nights 
(OnCalendar=Sun *-*-* 00:00:00). 

## Final Thoughts
When nodes are deployed in numbers ranging from 10s of thousands into 
the millions, we need to think differently about how we interact with 
the fleet. Also as connectivity increases with systems and devices, the
importance of keeping everything updated while minimizing downtime and 
application disruptions also become critical. The example kickstarts 
demonstrate how to configure nodes to automatically stay current on
available updates. These concepts can be built upon and adapted for 
many other use cases. 

