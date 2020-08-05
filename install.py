#!/usr/bin/python3

import argparse
import contextlib
import gc
import http.server
import os
import subprocess
import sys
import tempfile
import threading
from functools import partial
from string import Template


RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"


KICKSTART_TEMPLTE = """
lang en_US.UTF-8
keyboard us
timezone UTC
zerombr
clearpart --all --initlabel
autopart --type=plain --fstype=xfs --nohome
poweroff
text
network --bootproto=dhcp
user --name=core --groups=wheel --password=edge
services --enabled=ostree-remount
ostreesetup --nogpg --url=http://10.0.2.2:8000/repo/ --osname=rhel --remote=edge --ref=rhel/8/x86_64/edge
"""


class HttpHandler(http.server.SimpleHTTPRequestHandler):
    default_request_version = 'HTTP/1.1'

    def log_request(self, code=None, size=None):
        if code == 404:
            print(f"{self.path} not found")

    def finish(self):
        gc.collect()


class HttpServer(http.server.ThreadingHTTPServer):
    def server_activate(self):
        self.socket.listen(128)


def run(args):
    subprocess.run(args, check=True)


def start_install(disk, iso):
    p = subprocess.Popen(
        ["qemu-system-x86_64" ,
         "-m", "2048",
         "-enable-kvm",
         "-device", "virtio-net-pci,netdev=n0",
         "-netdev","user,id=n0,net=10.0.2.0/24",
         "-drive", f"file={disk}",
         "-cdrom", iso,
         "-nographic", "-display", "none"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        close_fds=True)
    return p


@contextlib.contextmanager
def serv_commit(port, repodir):
    handler = partial(HttpHandler, directory=repodir)

    with HttpServer(("", port), handler) as httpd:
        server_thread = threading.Thread(target=httpd.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        try:
            yield httpd
        finally:
            httpd.shutdown()


def prepare_kickstart(directory, **subst):
    path = os.path.join(directory, "kickstart.ks")
    tpl = Template(KICKSTART_TEMPLTE)
    data = tpl.substitute(**subst)
    with open(path, "w") as f:
        f.write(data)
    return path


def main(tmp):
    parser = argparse.ArgumentParser(description="Install ostree commit")
    parser.add_argument("commit", metavar="COMMIT", type=os.path.abspath,
                        help="commit, in tar form")
    parser.add_argument("iso", metavar="ISO", type=os.path.abspath,
                        help="boot ISO to use to install the commit")
    parser.add_argument("--output", metavar="FILENAME", type=os.path.abspath,
                        default="disk.qcow2",
                        help="Name of the disk image output")
    args = parser.parse_args(sys.argv[1:])

    disk = args.output
    iso = args.iso
    boot = os.path.join(tmp, "bootiso.iso")
    port = 8000

    kickstart = prepare_kickstart(tmp)

    commit = os.path.join(tmpdir, "commit")
    os.makedirs(commit)
    command = [
        "tar",
        "-x",
        "--auto-compress",
        "-f", args.commit,
        "-C", commit
    ]
    subprocess.run(command,
                   stdout=sys.stderr,
                   check=True)

    run(["./mkboot",
         iso,
         "--verbose",
         "--output", boot,
         "--kickstart", kickstart,
         "--kargs", "console=ttyS0"])

    run(["rm", "-f", disk])
    run(["qemu-img", "create", "-f", "qcow2", disk, "5G"])

    with serv_commit(port, commit) as httpd:
        try:
            p = start_install(disk, boot)
            for line in p.stdout:
                line = line.decode("utf-8").rstrip()
                print(line)
                if line == "Red Hat Enterprise Linux 8.3 Beta (Ootpa)":
                    break
            print(f"{BOLD}Installation done.{RESET}")
        except KeyboardInterrupt:
            httpd.shutdown()
            p.terminate()
            try:
                p.communicate(timeout=10)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                p.kill()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(dir="/var/tmp") as tmpdir:
        main(tmpdir)
