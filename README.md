# WifiCities

Your own portable website, broadcasting from your pocket.

WifiCities turns an ESP32 into a personal website. It broadcasts a WiFi network — when someone connects, a captive portal opens your site. No internet. No cloud. Just you and whoever's nearby.

Carry it on the bus, at a cafe, on a trip. Strangers find your site by connecting to your WiFi.

## Quick Start

```bash
git clone https://github.com/mhd12/wificities.git
cd wificities
./quickstart.sh
```

The script installs dependencies, walks you through creating your site (name, colors, etc.), and builds it. Then:

```bash
cd my-wificity
../wificities serve        # preview at localhost:8080
```

Plug in your ESP32 and flash:

```bash
../wificities flash
```

Done. Your ESP32 is now broadcasting your wificity.

## What You Get

- **WiFi captive portal** — connect to the network, site opens automatically
- **Guestbook** — visitors can leave messages that persist
- **Visitor counter** — see how many people have visited
- **8 color palettes** — midnight, sunset, ocean, forest, cyberpunk, vaporwave, terminal, newspaper
- **3 header styles** — banner, minimal, centered
- **Themes** — switch entire looks, keep your content
- **Plugins** — add features (frontend widgets or backend API extensions)
- **Works offline** — no internet needed, ever

## Customize

```bash
../wificities config                    # interactive menu
../wificities config palette vaporwave  # change colors
../wificities config header centered    # change header style
../wificities config set bio "new bio"  # change any value
../wificities theme switch geocities-flame  # swap theme
../wificities plugin add guestbook-widget   # add a plugin
```

After changes:

```bash
../wificities build
../wificities flash --only filesystem   # fast, skips firmware
```

## Edit Your Site

Your content lives in `my-wificity/content/`:

```
my-wificity/
├── config.json          # WiFi SSID, password, settings
├── wificities.json      # theme, pages, variables
└── content/
    ├── index.md         # homepage (Markdown)
    └── about.md         # about page
```

Edit the `.md` files with any text editor. Markdown gets converted to HTML during build.

**Want raw HTML instead?** Run `./quickstart.sh` and pick `(none)` as the theme — you get a `public/` folder with full control.

## Requirements

- Python 3.9+
- An ESP32 board (tested with ESP-WROOM-32)
- USB cable

Dependencies (`click`, `mistune`) are installed automatically. `esptool` is needed only for flashing (`pip install esptool`).

## Available Themes

| Theme | Description |
|-------|-------------|
| `default` | Clean retro theme with 8 color palettes and 3 header styles |
| `geocities-flame` | Flames, stars, marquees — full 1999 aesthetic |

## Available Plugins

| Plugin | Type | Description |
|--------|------|-------------|
| `guestbook-widget` | frontend | Guestbook form + entries |
| `visitor-counter` | frontend | Retro hit counter |

## Project Structure

```
wificities/
├── firmware/          # ESP32 firmware (C++/Arduino)
├── cli/               # CLI tool (Python)
├── themes/            # Built-in themes
├── plugins/           # Built-in plugins
├── quickstart.sh      # One-command setup
└── Makefile           # make build, make flash, etc.
```

## How It Works

1. ESP32 starts a WiFi access point with your custom SSID
2. A DNS server resolves all domains to the ESP32
3. When a device connects, the OS detects a captive portal and opens it
4. Your static site is served from the ESP32's filesystem
5. APIs (guestbook, visitors) run on the ESP32 firmware

## Make Your Own Theme

A theme is just HTML/CSS with template syntax:

```
my-theme/
├── theme.json
├── layouts/base.html      # outer shell
├── templates/home.html    # page templates
├── partials/header.html   # reusable blocks
└── assets/style.css       # styles
```

Template syntax: `{{variable}}`, `{{> partial}}`, `{{#if cond}}`, `{{#each list}}`.

## Make Your Own Plugin

**Frontend plugin** (no recompilation): HTML/CSS/JS widget that calls existing APIs.

**Backend plugin** (needs PlatformIO): C/C++ code that adds new API endpoints via the Plugin C API. Routes are isolated with `ScopedServer` — plugins can't hijack each other.

See `plugins/guestbook-widget/` for a frontend example.

## License

MIT
