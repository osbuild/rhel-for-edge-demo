#!/usr/bin/python3

import argparse
import functools
import json
import os
import subprocess
import sys
import tempfile


def run_ostree(*args, _input=None, _check=True, _stderr=sys.stderr, **kwargs):
    args = list(args) + [f'--{k}={v}' for k, v in kwargs.items()]
    if _stderr is None:
        _stderr = subprocess.DEVNULL
    res = subprocess.run(["ostree"] + args,
                         encoding="utf-8",
                         stdout=subprocess.PIPE,
                         stderr=_stderr,
                         input=_input,
                         check=_check)
    return res


def main(tmp):
    parser = argparse.ArgumentParser(description="Import an ostree commit")
    parser.add_argument("commit", metavar="COMMIT", type=os.path.abspath,
                        help="commit, in tar form")
    parser.add_argument("--repo", metavar="DIRECTORY", type=os.path.abspath,
                        default="repo",
                        help="Name of the target repository")
    args = parser.parse_args(sys.argv[1:])

    repo = args.repo
    print(f"repo:   {repo}")

    ostree = functools.partial(run_ostree, repo=repo)

    if not os.path.exists(repo):
        ostree("init", mode="archive-z2")

    # Extract the commit
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


    with open(os.path.join(commit, "compose.json"), "r") as fp:
        info = json.load(fp)

    commit_id = info["ostree-commit"]
    ref = info["ref"]
    parent = None

    print(f"commit: {commit_id}")
    print(f"ref:    {ref}")

    ostree("pull-local",
           os.path.join(commit, "repo"),
           ref)

    ostree("summary", "--update")

    res = ostree("rev-parse", f"{ref}^", _check=False, _stderr=None)
    if res.returncode == 0:
        parent = res.stdout.strip()
        print(f"parent: {parent}")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(dir="/var/tmp") as tmpdir:
        main(tmpdir)
