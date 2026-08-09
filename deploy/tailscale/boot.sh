#!/bin/sh
set -e

/usr/local/bin/containerboot &

for i in $(seq 1 60); do
  if [ -S /tmp/tailscaled.sock ]; then
    break
  fi
  sleep 2
done

if [ -n "$TS_AUTH_TOKEN" ]; then
  tailscale login --authkey="$TS_AUTH_TOKEN" || true
fi

sleep 3
tailscale set --hostname=digital-campus || true
tailscale funnel --bg 3000 || tailscale serve --set-path / 3000 || true

wait