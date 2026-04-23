# WifiCities

Your own portable website, broadcasting from your pocket.

Turn an ESP32 into a personal website. It broadcasts a WiFi network — when someone connects, your site opens automatically. No internet needed.

## Setup

```
git clone https://github.com/mhd12e/wificities.git
cd wificities
./wificities
```

First run installs everything automatically (Python venv, dependencies, compiles firmware). Then:

```
./wificities init my-site
./wificities serve
./wificities flash
```

All commands run from the repo root. No global install, nothing touches your system.

## Commands

```
./wificities init <name>       # create a new site
./wificities build             # build for ESP32
./wificities serve             # preview at localhost:8080
./wificities flash             # flash to ESP32
./wificities config            # interactive customization
./wificities config palette    # change color scheme
./wificities config header     # change header style
./wificities config set K V    # set any value
./wificities theme list        # show themes
./wificities theme switch X    # change theme
./wificities plugin list       # show plugins
./wificities plugin add X      # add a plugin
./wificities validate          # check for issues
./wificities uninstall         # remove venv and build cache
```

## Customize

The interactive config menu lets you change everything:

- **Color palette** — 8 presets: midnight, sunset, ocean, forest, cyberpunk, vaporwave, terminal, newspaper
- **Individual colors** — tweak any color after picking a palette
- **Header style** — banner, minimal, or centered
- **Fonts** — 5 presets or custom CSS fonts
- **Toggle features** — guestbook, visitor counter, sidebar, marquee, construction banner

After changes: `./wificities build && ./wificities flash --only filesystem`

## Edit Content

```
my-site/
├── config.json          # WiFi SSID, settings
├── wificities.json      # theme, pages, colors
└── content/
    ├── index.md         # homepage (Markdown)
    └── about.md         # about page
```

Want raw HTML? Pick `(none)` as theme during init.

## Requirements

- Python 3.9+
- ESP32 board (tested with ESP-WROOM-32)
- USB cable

Everything else is handled by `./wificities`.

## Uninstall

```
./wificities uninstall    # removes venv, build cache
rm -rf wificities/        # remove the whole thing
```

Nothing is installed system-wide. Delete the folder and it's gone.

## License

MIT
