# WifiCities

Your own portable website, broadcasting from your pocket.

Turn an ESP32 into a personal website. It broadcasts a WiFi network — when someone connects, your site opens automatically. No internet needed.

## Setup

```
git clone https://github.com/mhd12e/wificities.git
cd wificities
./wificities
```

First run installs everything automatically. Then:

```
./wificities init my-site
./wificities build
./wificities serve           # preview
./wificities flash           # flash to ESP32
```

## Themes & Plugins

Everything is a git repo. Install by name (verified) or by URL (custom):

```
./wificities theme list
./wificities theme add default
./wificities theme switch geocities-flame

./wificities plugin list
./wificities plugin add guestbook
./wificities plugin add visitor-counter
./wificities plugin add https://github.com/user/custom-plugin
```

Update installed packages:

```
./wificities theme update
./wificities plugin update
```

### Verified Themes

| Theme | Description |
|-------|-------------|
| `default` | 8 color palettes, 3 header styles, fully customizable |
| `geocities-flame` | Under construction since 1999. Full retro aesthetic. |

### Verified Plugins

| Plugin | Description |
|--------|-------------|
| `guestbook` | Visitors leave messages that persist |
| `visitor-counter` | Retro hit counter with digit display |

## Customize

```
./wificities config                    # interactive menu
./wificities config palette vaporwave  # change colors
./wificities config header centered    # change header
./wificities config set bio "hi"       # set any value
```

## Make Your Own

A theme or plugin is just a git repo. Push to GitHub, install by URL.

**Theme:** `theme.json` + `layouts/` + `templates/` + `partials/` + `assets/`

**Plugin:** `plugin.json` + `frontend/` (HTML/CSS/JS)

```
./wificities theme add https://github.com/you/your-theme
./wificities plugin add https://github.com/you/your-plugin
```

## Requirements

- Python 3.9+
- ESP32 board (tested with ESP-WROOM-32)
- USB cable

## Uninstall

```
./wificities uninstall
```

Nothing is installed system-wide. Delete the folder and it's gone.

## License

MIT
