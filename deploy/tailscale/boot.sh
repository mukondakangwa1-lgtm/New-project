#!/bin/sh
set -e

mkdir -p /var/lib/tailscale
tailscaled \
  --tun=userspace-networking \
  --state=/var/lib/tailscale/tailscaled.state \
  --port=0 &

for i in $(seq 1 60); do
  if [ -S /var/run/tailscale/tailscaled.sock ]; then
    break
  fi
  sleep 2
done

if [ -n "$TS_AUTH_TOKEN" ] && tailscale status 2>&1 | grep -qi "logged out"; then
  tailscale login --authkey="$TS_AUTH_TOKEN" || true
fi

sleep 3
tailscale set --hostname=digital-campus || true
tailscale funnel --bg 3000 || true

wait