#!/usr/bin/env python3

import argparse
import os
import platform
import shutil
import subprocess
import sys


RESET = "\033[0m"
BOLD = "\033[1m"


def genisoimage(rundir, datdir):
    args = [
        "genisoimage",
        "-input-charset", "utf-8",
        "-output", f"{rundir}/cloudinit.iso",
        "-volid", "cidata",
        "-joliet",
        "-rock",
        "-quiet",
        f"{datdir}/user-data",
        f"{datdir}/meta-data"]

    subprocess.run(args, check=True)


def main():
    parser = argparse.ArgumentParser(description="Boot virtual machine images")
    parser.add_argument('--memory', default=2048, help='Memory of the machine')
    parser.add_argument('--persist', default=False, action="store_true")
    parser.add_argument('--verbose', default=False, action="store_true")
    parser.add_argument('--cloud-init', default="cloud-init")
    parser.add_argument('image', type=str, help="The image to boot")
    parser.set_defaults(architecture='x86_64')
    subparsers = parser.add_subparsers(help='commands')

    parser_sub = subparsers.add_parser("x86_64", help='x64 architecture',
                                       aliases=['x64'])
    parser_sub.add_argument('-U', '--uefi', dest="uefi", action='store_true', default=False,
                            help='Boot via UEFI')
    parser_sub.add_argument('-S', '--secureboot', dest="secureboot", action='store_true', default=False,
                            help='Boot via UEFI and enable SecureBoot')
    parser_sub.set_defaults(architecture='x86_64')

    parser_sub = subparsers.add_parser("aarch64", help='ARM 64 architecture')
    parser_sub.set_defaults(architecture='aarch64')

    argv, extra = parser.parse_known_args()
    argv = vars(argv)

    runtimedir = os.getenv("XDG_RUNTIME_DIR", default="/tmp")

    cfgdir = os.path.abspath(argv["cloud_init"])
    rundir = os.path.join(runtimedir, "vm-cloud-init")
    datdir = os.path.join(rundir, "data")

    if argv["verbose"]:
        print(f"cfgdir: {cfgdir}")
        print(f"rundir: {rundir}")

    shutil.rmtree(rundir, ignore_errors=True)
    os.makedirs(rundir, exist_ok=True)
    shutil.copytree(cfgdir, datdir)

    genisoimage(rundir, datdir)

    arch = argv["architecture"]

    if arch == "x86_64":
        args = ['qemu-system-x86_64']
        if argv.get("secureboot", False):
            args += ["-drive",
                     "file=/usr/share/OVMF/OVMF_CODE.secboot.fd,if=pflash,format=raw,unit=0,readonly=on",
                     "-drive",
                     "file=/usr/share/OVMF/OVMF_VARS.secboot.fd,if=pflash,format=raw,unit=1,readonly=off",
                     "-machine",
                     "q35"]
        elif argv.get("uefi", False):
            args += ["-drive", "file=/usr/share/OVMF/OVMF_CODE.fd,if=pflash,format=raw,unit=0,readonly=on"]
    elif arch == "aarch64":
        args = ['qemu-system-ppc64',
                "-M", "virt",
                "-bios", "/usr/share/edk2/aarch64/QEMU_EFI.fd",
                "-boot", "efi",
                "-cpu", "cortex-a57"]
    else:
        print("unsupported architecture", file=sys.stderr)
        sys.exit(1)

    if platform.processor() == arch:
        args += ['-enable-kvm']

    if not argv["persist"]:
        args += ["-snapshot"]

    portfwd = {
        2222:22,
        9091:9090,
        8000:8000,
        8080:8080,
        8081:8081,
        8082:8082,
        8083:8083

    }

    for local, remote in portfwd.items():
        print(f"port {BOLD}{local}{RESET} → {BOLD}{remote}{RESET}")

    fwds = [f"hostfwd=tcp::{h}-:{g}" for h, g in portfwd.items()]

    # create a new mac address based on our machine id
    with open("/etc/machine-id", "r") as f:
        data = f.read().strip()

    maclst = ["FE"] + [data[x:x+2] for x in range(-12, -2, 2)]
    macstr = ":".join(maclst)

    print(f"MAC: {BOLD}{macstr}{RESET}")

    args += [
        "-m", str(argv["memory"]),
        f"-cdrom", f"{rundir}/cloudinit.iso",
        "-device", f"virtio-net-pci,netdev=n0,mac={macstr}",
        "-netdev", "user,id=n0,net=10.0.2.0/24," + ",".join(fwds),
    ] + extra + [argv["image"]]

    if argv["verbose"]:
        print(" ".join(args))

    try:
        res = subprocess.run(args, check=False)
    except KeyboardInterrupt:
        print("Aborted")
        return -1

    return res.returncode


if __name__ == "__main__":
    sys.exit(main())
