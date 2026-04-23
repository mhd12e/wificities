# WifiCities

Your own portable website, broadcasting from your pocket.

Turn an ESP32 into a personal website. It broadcasts a WiFi network — when someone connects, your site opens automatically. No internet needed.

Carry it on the bus, at a cafe, on a trip. Anyone nearby can visit your site just by connecting to your WiFi.

## Setup

```
git clone https://github.com/mhd12e/wificities.git
cd wificities
./quickstart.sh
```

That's it. The script installs everything, walks you through creating your site, and compiles the firmware. When it's done:

```
cd my-wificity
wificities serve          # preview at localhost:8080
wificities flash          # plug in ESP32, flash it
```

The `wificities` command works from anywhere after setup.

## Customize

```
wificities config                    # interactive menu
wificities config palette vaporwave  # change colors
wificities config header centered    # change header style
wificities config set bio "hi"       # change any value
wificities theme switch geocities-flame
wificities plugin add guestbook-widget
```

After changes: `wificities build && wificities flash --only filesystem`

## Edit Content

Your site lives in `my-wificity/content/`. Edit the Markdown files:

```
my-wificity/
├── config.json          # WiFi SSID, settings
├── wificities.json      # theme, pages, colors
└── content/
    ├── index.md         # homepage
    └── about.md         # about page
```

Want raw HTML? Run quickstart and pick `(none)` as theme.

## Color Palettes

midnight, sunset, ocean, forest, cyberpunk, vaporwave, terminal, newspaper

## Themes

- `default` — clean retro, 8 palettes, 3 header styles
- `geocities-flame` — full 1999 GeoCities aesthetic

## Plugins

- `guestbook-widget` — visitors leave messages
- `visitor-counter` — retro hit counter

## Requirements

- Python 3.9+
- ESP32 board (tested with ESP-WROOM-32)
- USB cable

Everything else is installed automatically by `./quickstart.sh`.

## How It Works

1. ESP32 broadcasts a WiFi network with your custom name
2. A DNS server on the ESP32 catches all requests
3. Captive portal triggers automatically on iOS, Android, Windows
4. Your site is served from the ESP32's flash storage
5. Guestbook entries and visitor count persist across reboots

## License

MIT
