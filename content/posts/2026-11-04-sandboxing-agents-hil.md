title: Sandboxing an AI agent that needs a debug probe
date: 2026-11-04
---
I use Claude Code every day, often in auto mode. A few days ago I stopped and asked a simple
question: what is actually keeping this agent inside the project folder?

The honest answer was: not much. Permission prompts and rules are checks inside the
application. They are not isolation. A shell command started by the agent ran as my user,
with my home directory, my SSH key and my network. A prompt injection hidden in a README,
a dependency or a web page could turn that into a real problem.

This note collects what I found while looking at OS-level sandboxing, and where it stops
working for embedded development with hardware in the loop.

## What the sandbox actually does

Claude Code has a native sandbox. On Linux it is built on **bubblewrap** (`bwrap`), the same
building block used by Flatpak. bwrap contains almost no security logic of its own: it asks
the kernel to start a process inside new **namespaces** (mount, user, pid, net), so the process
gets a private view of the filesystem, the process list and the network. No VM, no overhead.

The filesystem view is built in layers, and the last mount wins:

```
--ro-bind / /            whole system, read-only
--tmpfs ~/.ssh           cover the keys with an empty folder
--bind <project>         re-open only the project for writing
--unshare-net            no network interface of its own
```

The network goes out through a single door: a socket bridged to a proxy running in Claude
Code, which only lets through the domains in an allowlist.

The first thing I had to get straight is that there are **two separate layers**:

```
Claude Code (main process, NOT sandboxed)
  ├── Read / Edit / WebFetch ──► permission rules (application level)
  └── Bash ──► bubblewrap     ──► kernel-enforced isolation
```

The sandbox only covers Bash commands and their children. The built-in file tools are covered
only by the permission rules. So every sensitive path has to be denied **in both places**.

## Findings

**Reads are open by default.** The sandbox restricts writes to the project and the temp
folder, but it can read almost everything, `~/.ssh` included, until you deny it explicitly.
The `denyRead` list is the part of the configuration that matters most.

**Unix sockets are files, and the network namespace does not stop them.** My user is in the
`docker` group. Talking to `/run/docker.sock` is equivalent to root
(`docker run -v /:/host ...`). Cutting the network does nothing here, because a Unix socket is
reached through the filesystem, and the service behind it runs outside the bubble with its own
privileges. The fix is to hide the socket with `denyRead`. Blocking Unix sockets entirely
needs a seccomp filter, which is an optional component.

One open-source agent sandbox I reviewed had exactly this hole: it carefully built a bwrap
jail, then mounted its terminal multiplexer's control socket inside it, writable. One command
from inside and you are running on the host. Good building blocks, one socket, no sandbox.

**Two settings decide whether the sandbox is real:**

```json
"sandbox": {
  "enabled": true,
  "failIfUnavailable": true,
  "allowUnsandboxedCommands": false
}
```

Without `failIfUnavailable`, if bwrap cannot start, Claude Code silently falls back to running
without a sandbox. Without `allowUnsandboxedCommands: false`, the agent can retry a blocked
command outside the sandbox, and in auto mode the only thing deciding is a classifier.

## Where embedded breaks the recipe

For web or backend work this is close to a solved problem. In my day job, though, the agent
has to compile, flash the board and read back what the firmware says through the J-Link or a
serial port. That is where things get interesting.

**The probe disappears.** The sandbox runs bwrap with `--dev /dev`, which creates a minimal
`/dev` with only `null`, `zero`, `random`, `tty` and a few others. No `/dev/bus/usb/...`, no
`/dev/ttyACM*`. `JLinkExe` starts and reports that no probe is connected. You cannot add the
device back either: the sandbox code explicitly skips any path under `/dev` in its allow
lists.

**localhost is private.** A `JLinkGDBServer` started inside the sandbox is unreachable from
the IDE outside, and the other way round. Network probes on raw TCP don't pass through the
HTTP proxy at all.

**The obvious workaround reopens the host.** Put `JLinkExe` in `excludedCommands` and it runs
outside the sandbox, driven by command files the agent wrote. J-Link Commander can read and
write host files:

```
savebin ~/.bashrc 0x20000000 0x100     overwrite a host file with target RAM
loadfile ~/.ssh/id_ed25519 0x20000000  read a secret into the target
```

GDB outside the sandbox is worse: `shell` and `python` run anything. Handing the agent a
general-purpose debug tool is the same as removing the sandbox.

## What I'm evaluating

A few small, trusted wrappers, stored outside the project so the agent cannot edit them, and
listed as the only excluded commands:

- `hil-flash <file>` accepts only a file inside the project's `build/` folder. Device,
  interface and speed come from the wrapper's own config. It generates the J-Link script
  itself, with `loadfile`, reset, go and quit only.
- `hil-reset` resets the target.
- `hil-read-mem <addr> <len>` prints a bounded memory dump. It never writes a file on the host.

For reading, no exception at all: a separate logger writes serial and RTT output to a log file
inside the project, and the agent reads it from within the sandbox.

The agent can then build, flash, reset and observe. It cannot ask the probe to touch the host.

## What no sandbox solves

The firmware is the agent's code, and it runs on the target. It can write the option bytes by
itself. On an STM32, setting read protection to level 2 locks the chip permanently. No host
isolation prevents that. The only answer I have is organisational: **dedicated HIL boards,
never unique or production hardware.**

## Still open

Interactive debugging. Breakpoints and stepping are where an agent would help most, and where
a narrow wrapper is hardest to design without handing over a general-purpose debugger.

If you run AI agents against real hardware, I'd like to know where you draw the line: a
dedicated HIL runner, a VM with USB passthrough, a human in the loop for every flash? You can
find me on [LinkedIn](https://www.linkedin.com/in/alessandro-giuliani-02376a113/).
