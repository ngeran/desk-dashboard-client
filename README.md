# desk-dashboard-client

The Raspberry Pi display client for [desk-dashboard](../desk-dashboard). It is a
single static web page (no build step, no Node) that opens the shell's WebSocket
and renders whatever components currently exist — it has **zero hardcoded
component knowledge**, so adding/removing a component on the cluster changes this
display with no edit here.

## What it does

1. `GET <shell>/components` → the manifest list (titles, categories, schemas).
2. `WS   <shell>/stream`    → the merged envelope set, pushed every tick.
3. Renders one card per component from its envelope `data`, re-fetching
   `/components` whenever a new component id appears — so the display tracks the
   cluster automatically. Reconnects on disconnect.

## 1. On the cluster host — expose the shell

The shell Service is `NodePort 30080`. Get the host's LAN IP (single-node k3s →
it's the host IP):

```bash
kubectl get nodes -o wide --no-headers | awk '{print $1, $6}'   # e.g. nixos-btw 192.168.1.10
```

The Pi will connect to `http://192.168.1.10:30080`. (Home-LAN only — plain HTTP,
no auth.)

## 2. On the Pi — get the client

```bash
git clone git@github.com:ngeran/desk-dashboard-client.git
cd desk-dashboard-client
```

(Install Chromium once: `sudo apt install -y chromium`.)

## 3. Run it

```bash
./kiosk.sh http://192.168.1.10:30080
```

That opens Chromium in full-screen kiosk mode pointed at the shell. To develop on
a laptop instead, just open `index.html?shell=http://localhost:30080` in a browser
(with the backend running locally per the desk-dashboard README).

Change the shell URL any time via the "change" link in the footer.

## 4. Autostart on boot (optional)

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/desk-dashboard-client.service <<'EOF'
[Unit]
Description=desk-dashboard display client
After=graphical-session.target
[Service]
Environment=SHELL_URL=http://192.168.1.10:30080
ExecStart=/home/pi/desk-dashboard-client/kiosk.sh
Restart=always
[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now desk-dashboard-client.service
# (enable lingering so the user service runs without an active login:)
sudo loginctl enable-user pi
```

## Update

```bash
git pull        # then restart the kiosk / service
```

## Notes

- Rendering is intentionally generic (the client reads each component's data
  recursively and picks units from key names). Per-component polish can come
  later without changing the contract.
- If the Pi's clock is off, timestamps will look wrong — enable NTP
  (`sudo timedatectl set-ntp true`).
