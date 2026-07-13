# Security

## The short version

Kitty Terminal Pets must never compete with a shell for keyboard input. The installed config uses `allow_remote_control socket-only`; requests arriving through the terminal TTY are denied.

## What the controller can see

To place the pet, the controller asks Kitty for the active window's cursor coordinates. Kitty's response also contains screen text; that response is held in memory only long enough to parse the final cursor-position escape code and is immediately discarded. It is never logged, stored, or transmitted.

Pet and command state stay on the local machine. The project has no telemetry.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository rather than opening a public issue with exploit details. Include the Kitty version, Linux distribution, and the smallest reproduction you can share.

## Third-party pets

Pet files are data loaded from local directories. The project parses JSON and image files but never executes code from a pet package. Only install artwork you are allowed to use.
