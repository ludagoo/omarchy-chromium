#!/usr/bin/env python3
"""remsg.py REPO BRANCH MSG... : give the last len(MSG) commits of BRANCH the
messages in the MSG files (oldest first). Trees, authors and author dates are
kept; the working tree and index are not touched. Prints old -> new."""
import os, subprocess, sys

repo, branch, msgs = sys.argv[1], sys.argv[2], sys.argv[3:]


def git(*args, env=None, inp=None):
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True,
                          text=True, env=env, input=inp).stdout.strip()


commits = git("rev-list", "--reverse", f"{branch}~{len(msgs)}..{branch}").split()
assert len(commits) == len(msgs), (commits, msgs)
parent = git("rev-parse", f"{branch}~{len(msgs)}")
for c, m in zip(commits, msgs):
    name, email, date = git("log", "-1", "--format=%an%x00%ae%x00%aD", c).split("\0")
    env = dict(os.environ, GIT_AUTHOR_NAME=name, GIT_AUTHOR_EMAIL=email, GIT_AUTHOR_DATE=date,
               GIT_COMMITTER_NAME=name, GIT_COMMITTER_EMAIL=email)
    msg = open(m).read().rstrip() + "\n"
    if git("log", "-1", "--format=%B", c).rstrip() + "\n" == msg and \
            git("rev-parse", f"{c}^") == parent:
        parent = c
        continue
    parent = git("commit-tree", f"{c}^{{tree}}", "-p", parent, env=env, inp=msg)
old = git("rev-parse", branch)
ref = git("symbolic-ref", "HEAD") if branch == "HEAD" else f"refs/heads/{branch}"
if old != parent:
    git("update-ref", ref, parent, old)
print(branch, old[:12], "->", parent[:12])
