# WifiCities

> Your own portable website, broadcasting from your pocket.

WifiCities is an open-source project that turns an ESP32 into a personal, portable website. Each ESP32 runs as a WiFi access point — when someone nearby connects, a captive portal opens and they're on your site. No internet required. Like Neocities, but physical.

---

## Concept

- One ESP32 = one wificity
- The ESP32 broadcasts a WiFi network with a custom SSID (your "storefront sign")
- When someone connects, a captive portal automatically opens your personal site
- Your site can have anything: about page, mini games, articles, art, links, a guestbook
- Visitors can sign your guestbook — entries persist for the next visitor
- You carry it with you: on the bus, at a cafe, on a trip
- No internet. No cloud. Just you and whoever's nearby.
- Retro GeoCities aesthetic — max skeuomorphism, beveled buttons, tiled backgrounds, visitor counters, under construction gifs

---

## Architecture Overview

```
┌───────────────────────────────────────────────────┐
│                CLI Tool (Python)                   │
│   init │ build │ flash │ serve │ plugin │ theme    │
├────────────────┬──────────────────────────────────┤
│  Theme Engine  │         Plugin System             │
│                │  ┌────────────┬───────────────┐   │
│  layouts       │  │  Frontend  │   Backend      │   │
│  templates     │  │  HTML/CSS  │   C/C++        │   │
│  partials      │  │  JS/assets │   Plugin API   │   │
│  variables     │  │            │   ScopedServer  │   │
│  Markdown→HTML │  │            │   Storage       │   │
│                │  └────────────┴───────────────┘   │
├────────────────┴──────────────────────────────────┤
│                 Build Pipeline                      │
│  template render → asset collect → size check →     │
│  firmware compile (if needed) → LittleFS image      │
├───────────────────────────────────────────────────┤
│                 ESP32 Firmware                      │
│  WiFi AP │ DNS Server │ Captive Portal │            │
│  Static File Server (folder-based routing) │        │
│  Core APIs │ Plugin Loader │ Admin Auth             │
├───────────────────────────────────────────────────┤
│                 LittleFS (~2.5MB)                  │
│  config.json │ /data/ │ /public/                    │
└───────────────────────────────────────────────────┘
```

### Core Rules

1. The **core firmware** (WiFi AP, DNS, captive portal, file server, built-in APIs) is stable and shared by everyone
2. **Themes** only touch frontend files (HTML/CSS/JS/assets) — they are processed at build time into flat static HTML
3. **Frontend plugins** only touch frontend files — no recompilation needed
4. **Backend plugins** extend the firmware through the Plugin C API — requires recompilation, but the CLI handles it automatically
5. Users without backend plugins don't need PlatformIO — pre-built firmware binaries are provided

---

## 1. Firmware (Backend)

### 1.1 WiFi Access Point

- Broadcasts a WiFi network using the SSID from `config.json`
- Optional WPA2 password (empty = open network, recommended for discoverability)
- Configurable WiFi channel (default: 1, useful when multiple wificities are nearby to avoid interference)
- Max simultaneous connections: configurable (default: 8, ESP32 supports up to 10)
- Works across ESP32, ESP32-S2, ESP32-S3, ESP32-C3

### 1.2 DNS Server

A lightweight DNS server runs on the ESP32 that resolves **all domain queries** to `192.168.4.1` (the ESP32's IP). This is what makes the captive portal work — any HTTP request from a connected device hits our web server regardless of what domain they requested.

### 1.3 Captive Portal

When a device connects to WiFi, the OS checks internet connectivity by hitting known URLs. Because our DNS resolves everything to us, those requests land on our server. We handle them to trigger the captive portal popup.

#### OS-Specific Detection

| OS | Detection URL | Expected Response | Our Response |
|----|--------------|-------------------|--------------|
| iOS/macOS | `http://captive.apple.com/hotspot-detect.html` | `<HTML>...<TITLE>Success</TITLE>...</HTML>` | 302 redirect to `http://192.168.4.1/` |
| Android | `http://connectivitycheck.gstatic.com/generate_204` | 204 No Content | 302 redirect to `http://192.168.4.1/` |
| Android (alt) | `http://clients3.google.com/generate_204` | 204 No Content | 302 redirect to `http://192.168.4.1/` |
| Samsung | `http://connectivitycheck.samsung.com/generate_204` | 204 No Content | 302 redirect to `http://192.168.4.1/` |
| Windows | `http://www.msftconnecttest.com/connecttest.txt` | `Microsoft Connect Test` | 302 redirect to `http://192.168.4.1/` |

By returning a 302 redirect instead of the expected response, we trick the OS into thinking it's a captive portal that needs interaction → it opens the portal UI.

#### Behavior by OS

- **iOS**: Opens CNA (Captive Network Assistant) — a mini-browser with limited JS. Works fine for most static sites. Themes should include an "Open in Safari" link for heavier content (games etc.)
- **Android**: Opens Chrome or default browser — full browser, no limitations
- **Windows**: Opens Edge — full browser
- **macOS**: Opens a popup WebView — similar to iOS CNA

#### Fallback

If the captive portal popup doesn't trigger (some devices suppress it), the user can manually open a browser and navigate to any URL — our DNS will resolve it to the site anyway. As a convenience, the firmware also registers mDNS so `http://wificity.local/` works on devices that support it.

### 1.4 Static File Server with Folder-Based Routing

The firmware serves files from `/public/` using **folder-based routing** — clean URLs derived from the directory structure.

#### How routing works

```
public/
├── index.html              → /
├── about/
│   └── index.html          → /about
├── games/
│   ├── index.html          → /games
│   └── snake/
│       └── index.html      → /games/snake
├── links/
│   └── index.html          → /links
├── style.css               → /style.css
├── 404.html                → custom 404 page
└── images/
    └── flames.gif          → /images/flames.gif
```

#### Routing rules (in priority order)

1. **API routes**: `/api/*` → handled by firmware API layer, never hits filesystem
2. **Admin routes**: `/admin/*` → handled by firmware admin layer
3. **Exact file match**: `/style.css` → serves `public/style.css`
4. **Directory index**: `/about` → serves `public/about/index.html`
5. **HTML fallback**: `/about` → tries `public/about.html` (for people who prefer flat files over folders)
6. **404**: If nothing matches → serves `public/404.html` if it exists, otherwise a minimal built-in 404 page

#### Response details

- MIME types detected automatically from file extension
- No `.html` in URLs — clean paths only
- Trailing slashes normalized: `/about/` → `/about`
- Query strings passed through untouched
- **Cache headers**: Static assets (CSS, JS, images, fonts, audio) get `Cache-Control: max-age=86400` (1 day). HTML files get `Cache-Control: no-cache` (always fresh)
- **Supported MIME types**:

| Extension | MIME Type |
|-----------|----------|
| `.html` | `text/html` |
| `.css` | `text/css` |
| `.js` | `application/javascript` |
| `.json` | `application/json` |
| `.png` | `image/png` |
| `.jpg` `.jpeg` | `image/jpeg` |
| `.gif` | `image/gif` |
| `.ico` | `image/x-icon` |
| `.svg` | `image/svg+xml` |
| `.woff` `.woff2` | `font/woff` / `font/woff2` |
| `.mp3` | `audio/mpeg` |
| `.mid` `.midi` | `audio/midi` |
| `.wav` | `audio/wav` |
| `.txt` | `text/plain` |

### 1.5 Built-in APIs

REST endpoints built into the firmware. Sites and plugins can call them via `fetch()` from JavaScript.

#### `GET /api/guestbook`

Returns all guestbook entries, newest first.

```json
{
  "entries": [
    {
      "id": 12,
      "name": "CoolVisitor99",
      "message": "awesome site dude!! 🔥",
      "timestamp": 1713800000
    },
    {
      "id": 11,
      "name": "passerby",
      "message": "found this on the bus, rad",
      "timestamp": 1713799000
    }
  ],
  "count": 2,
  "max": 100
}
```

#### `POST /api/guestbook`

Create a guestbook entry.

**Request:**
```json
{
  "name": "CoolVisitor99",
  "message": "awesome site dude!! 🔥"
}
```

**Response (201):**
```json
{
  "ok": true,
  "id": 13
}
```

**Validation:**
- `name`: required, 1-32 characters, HTML tags stripped
- `message`: required, 1-256 characters, HTML tags stripped
- **Rate limit**: 1 entry per MAC address per 60 seconds (prevents spam)
- When entry count exceeds `guestbook_max_entries` from config, the oldest entry is dropped

**Response (429 — rate limited):**
```json
{
  "ok": false,
  "error": "rate_limited",
  "retry_after": 45
}
```

**Response (400 — validation error):**
```json
{
  "ok": false,
  "error": "validation",
  "message": "name is required"
}
```

#### `DELETE /api/guestbook/:id`

Delete a guestbook entry. Requires admin password.

**Request:**
```json
{
  "admin_password": "changeme"
}
```

**Response (200):**
```json
{ "ok": true }
```

**Response (401):**
```json
{ "ok": false, "error": "unauthorized" }
```

**Response (404):**
```json
{ "ok": false, "error": "not_found" }
```

#### `DELETE /api/guestbook`

Clear all guestbook entries. Requires admin password.

**Request:**
```json
{
  "admin_password": "changeme"
}
```

#### `GET /api/visitors`

Returns visitor statistics.

```json
{
  "total": 142,
  "current": 3
}
```

- `total` — all-time connection count. Persisted to disk. Incremented on each new device connection (by MAC address). Kept in RAM and flushed to disk every 10 increments or every 5 minutes, whichever comes first (to reduce flash wear).
- `current` — currently connected device count (real-time from WiFi layer).

#### `POST /api/visitors/reset`

Reset total visitor count. Requires admin password.

#### `GET /api/info`

Returns site metadata and system info.

```json
{
  "name": "Mhd's Wificity",
  "ssid": "✨ Mhd's Place ✨",
  "uptime": 3600,
  "version": "1.0.0",
  "storage": {
    "used": 512000,
    "total": 2560000,
    "free": 2048000
  },
  "plugins": ["polls", "shoutbox"],
  "visitors": {
    "total": 142,
    "current": 3
  }
}
```

### 1.6 Admin System

The owner can manage their wificity from any connected device by navigating to `http://192.168.4.1/admin`.

The admin page is a **built-in firmware page** (not a user file — it's always available regardless of what the user's site contains). It provides:

- View/delete guestbook entries
- View/reset visitor count
- View storage usage
- View system info (uptime, firmware version, connected devices)
- Restart ESP32

All admin actions require the `admin_password` from `config.json`. The admin page stores it in `sessionStorage` after first entry.

The admin page is minimal, functional HTML — not themed. It always works regardless of the user's site.

### 1.7 Error Handling

| Situation | Behavior |
|-----------|----------|
| `config.json` missing or corrupt | Use defaults: SSID = `"WifiCity"`, no password, admin_password = `"admin"` |
| `public/index.html` missing | Serve a built-in "Welcome to WifiCities — flash a site to get started" page |
| LittleFS full (on POST) | Return 507 Insufficient Storage, stop accepting writes |
| Plugin crashes during init | Log error, skip that plugin, continue serving site |
| Plugin crashes during request | Return 500 to that request, other routes unaffected |
| File not found | Serve `public/404.html` if it exists, otherwise built-in 404 |

### 1.8 Plugin Loader

On boot, the firmware loads all registered backend plugins. See [Section 5.4](#54-backend-plugins--the-plugin-c-api) for the full Plugin C API.

Boot sequence:
1. Initialize LittleFS
2. Read `config.json` (or use defaults)
3. Start WiFi AP with configured SSID
4. Start DNS server (resolve all → 192.168.4.1)
5. Register captive portal detection routes
6. Register built-in API routes (`/api/guestbook`, `/api/visitors`, `/api/info`)
7. Register admin routes (`/admin`)
8. **Initialize each registered plugin** (create storage, call `on_init`, call `register_routes`)
9. Register static file server (folder-based routing) as the catch-all handler
10. Start serving

---

## 2. Config

### 2.1 config.json (Runtime — flashed to ESP32)

```json
{
  "ssid": "✨ Mhd's Place ✨",
  "password": "",
  "admin_password": "changeme",
  "channel": 1,
  "max_connections": 8,
  "site_name": "Mhd's Wificity",
  "guestbook_max_entries": 100,
  "guestbook_max_name_length": 32,
  "guestbook_max_message_length": 256,
  "guestbook_rate_limit_seconds": 60,
  "plugins": {
    "polls": {
      "max_polls": 5,
      "allow_anonymous": true
    }
  }
}
```

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `ssid` | yes | `"WifiCity"` | WiFi network name. Max 32 chars. Your identity. |
| `password` | no | `""` | WiFi password. Empty = open network. |
| `admin_password` | yes | `"admin"` | Password for admin actions. |
| `channel` | no | `1` | WiFi channel (1-13). Change if interference. |
| `max_connections` | no | `8` | Max simultaneous WiFi clients (1-10). |
| `site_name` | no | `ssid` value | Human-readable site name for `/api/info`. |
| `guestbook_max_entries` | no | `100` | Max entries before oldest are dropped. |
| `guestbook_max_name_length` | no | `32` | Max chars for guestbook name. |
| `guestbook_max_message_length` | no | `256` | Max chars for guestbook message. |
| `guestbook_rate_limit_seconds` | no | `60` | Cooldown between entries per device. |
| `plugins` | no | `{}` | Plugin-specific config. Keys are plugin names. |

### 2.2 wificities.json (Build-time — project manifest, NOT flashed)

This file lives in the user's project folder and tells the CLI how to build the site.

**Theme mode:**
```json
{
  "mode": "theme",
  "theme": "geocities-flame",
  "pages": {
    "/": {
      "template": "home",
      "content": "content/index.md"
    },
    "/about": {
      "template": "page",
      "content": "content/about.md"
    },
    "/games": {
      "template": "page",
      "content": "content/games.md"
    },
    "/links": {
      "template": "links",
      "variables": {
        "links": [
          { "title": "Cool Site", "url": "#", "description": "a cool site" },
          { "title": "Another", "url": "#", "description": "another one" }
        ]
      }
    }
  },
  "variables": {
    "site_title": "Mhd's Wificity",
    "owner_name": "Mhd",
    "bio": "Welcome to my corner of the airwaves!",
    "show_guestbook": true,
    "show_visitor_counter": true,
    "bg_color": "#000033",
    "text_color": "#00ff00"
  },
  "plugins": {
    "guestbook-widget": "1.0.0",
    "visitor-counter": "1.0.0"
  }
}
```

**Raw mode:**
```json
{
  "mode": "raw",
  "plugins": {
    "guestbook-widget": "1.0.0"
  }
}
```

**No wificities.json at all**: Pure raw mode, no plugins. Just `config.json` + `public/` folder.

#### Page definition

Each page in `pages` maps a URL path to a template and content source:

| Field | Required | Description |
|-------|----------|-------------|
| `template` | yes | Which theme template to use (`home`, `page`, `gallery`, `links`, etc.) |
| `content` | no | Path to content file (`.md` or `.html`). Omit for data-driven pages. |
| `variables` | no | Page-specific variables. Override global variables for this page only. |

#### Variable resolution order

When the template engine encounters `{{some_var}}`, it looks up the value in this order:

1. **Page-specific variables** (from the page's `variables` in `wificities.json`)
2. **Global variables** (from top-level `variables` in `wificities.json`)
3. **Theme defaults** (from `theme.json` `variables[key].default`)
4. **Built-in variables** (auto-generated, see below)
5. **Empty string** (if nothing matched — no errors, just renders blank)

#### Built-in variables (always available)

| Variable | Value |
|----------|-------|
| `{{year}}` | Current year at build time (e.g., `2026`) |
| `{{build_date}}` | Build timestamp (e.g., `2026-04-22`) |
| `{{page_url}}` | Current page's URL path (e.g., `/about`) |
| `{{wificities_version}}` | CLI version |

---

## 3. Frontend (User Content)

### 3.1 Theme Mode (beginners)

```
my-wificity/
├── config.json              ← runtime config (gets flashed)
├── wificities.json          ← build manifest (pages, variables, plugins)
└── content/
    ├── index.md             ← homepage content (Markdown)
    ├── about.md             ← about page content
    ├── games.md             ← games page content
    └── assets/              ← user's own images (copied to build)
        ├── me.jpg
        └── cat.gif
```

Content files can be `.md` (Markdown — converted to HTML during build) or `.html` (used as-is). Markdown is recommended for simplicity.

User assets in `content/assets/` are copied to `build/public/assets/` and accessible at `/assets/filename`.

### 3.2 Raw Mode (power users)

```
my-wificity/
├── config.json
├── wificities.json          ← optional (only needed for plugins)
└── public/
    ├── index.html           ← entry point (required)
    ├── style.css
    ├── script.js
    ├── 404.html             ← custom 404 page (optional)
    ├── images/
    │   ├── bg-tile.gif
    │   └── flames.gif
    ├── about/
    │   └── index.html       ← /about
    └── games/
        ├── index.html       ← /games
        └── snake/
            └── index.html   ← /games/snake
```

No template engine, no Markdown processing. The CLI packages `public/` as-is.

### 3.3 Using APIs from your site

```html
<!-- Guestbook example -->
<div id="guestbook"></div>
<form id="gb-form">
  <input name="name" placeholder="your name" maxlength="32" required>
  <textarea name="message" placeholder="leave a message" maxlength="256" required></textarea>
  <button type="submit">Sign my guestbook!</button>
</form>
<div id="gb-error" style="display:none; color:red;"></div>

<script>
  fetch('/api/guestbook')
    .then(r => r.json())
    .then(data => {
      document.getElementById('guestbook').innerHTML = data.entries
        .map(e => `<p><b>${e.name}</b>: ${e.message}</p>`)
        .join('') || '<p><i>No entries yet. Be the first!</i></p>';
    });

  document.getElementById('gb-form').addEventListener('submit', e => {
    e.preventDefault();
    const form = new FormData(e.target);
    fetch('/api/guestbook', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: form.get('name'),
        message: form.get('message')
      })
    })
    .then(r => r.json())
    .then(data => {
      if (data.ok) location.reload();
      else {
        document.getElementById('gb-error').style.display = 'block';
        document.getElementById('gb-error').textContent =
          data.error === 'rate_limited'
            ? `Wait ${data.retry_after}s before posting again`
            : data.message;
      }
    });
  });
</script>
```

---

## 4. Themes & Templates

A theme provides the visual foundation — layouts, page templates, partials, and assets. The user picks a theme, writes content in Markdown, and the CLI bakes everything into flat static HTML during build.

### 4.1 Theme Structure

```
themes/
├── geocities-flame/
│   ├── theme.json
│   ├── layouts/
│   │   ├── base.html          ← standard layout (header, sidebar, footer)
│   │   └── fullwidth.html     ← no sidebar (for galleries, games)
│   ├── templates/
│   │   ├── home.html          ← homepage with welcome banner
│   │   ├── page.html          ← generic content page
│   │   ├── gallery.html       ← image gallery
│   │   └── links.html         ← bookmarks/links page
│   ├── partials/
│   │   ├── header.html        ← site banner with title + sparkle gifs
│   │   ├── footer.html        ← footer with copyright, visitor counter
│   │   ├── nav.html           ← navigation links
│   │   ├── sidebar.html       ← sidebar widgets area
│   │   └── guestbook.html     ← guestbook form + entries (uses /api/guestbook)
│   ├── assets/
│   │   ├── style.css          ← all the retro CSS
│   │   ├── theme.js           ← cursor trails, snow effects, etc.
│   │   ├── flames.gif
│   │   ├── stars-bg.gif
│   │   ├── under-construction.gif
│   │   ├── divider-rainbow.gif
│   │   ├── email-icon.gif
│   │   ├── new-blink.gif
│   │   └── cursor-sparkle.ani
│   └── preview.png            ← screenshot for `wificities theme list`
```

### 4.2 theme.json

```json
{
  "name": "GeoCities Flame",
  "description": "Under construction since 1999. Flames, stars, and beveled everything.",
  "author": "wificities",
  "version": "1.0.0",
  "layouts": {
    "base": {
      "description": "Standard layout with sidebar",
      "file": "layouts/base.html"
    },
    "fullwidth": {
      "description": "Full width, no sidebar",
      "file": "layouts/fullwidth.html"
    }
  },
  "templates": {
    "home": {
      "description": "Homepage with welcome banner and widgets",
      "layout": "base"
    },
    "page": {
      "description": "Generic content page",
      "layout": "base"
    },
    "gallery": {
      "description": "Image gallery with thumbnails",
      "layout": "fullwidth"
    },
    "links": {
      "description": "Bookmarks and cool links page",
      "layout": "base"
    }
  },
  "variables": {
    "site_title": {
      "type": "string",
      "description": "Your site's name",
      "default": "My Wificity"
    },
    "owner_name": {
      "type": "string",
      "description": "Your name or handle",
      "default": "Anonymous"
    },
    "bio": {
      "type": "text",
      "description": "A short bio or welcome message",
      "default": "Welcome to my corner of the airwaves!"
    },
    "bg_color": {
      "type": "color",
      "description": "Background color",
      "default": "#000033"
    },
    "text_color": {
      "type": "color",
      "description": "Text color",
      "default": "#00ff00"
    },
    "show_guestbook": {
      "type": "boolean",
      "description": "Show guestbook on homepage",
      "default": true
    },
    "show_visitor_counter": {
      "type": "boolean",
      "description": "Show visitor counter in footer",
      "default": true
    },
    "show_sidebar": {
      "type": "boolean",
      "description": "Show the sidebar",
      "default": true
    },
    "nav_links": {
      "type": "list",
      "description": "Navigation menu items",
      "default": [
        { "title": "Home", "url": "/" },
        { "title": "About", "url": "/about" },
        { "title": "Links", "url": "/links" }
      ]
    }
  }
}
```

Variable types (`string`, `text`, `color`, `boolean`, `list`) are used by the CLI during `wificities init` to show appropriate prompts. They don't affect template rendering — all variables are just replaced as values.

### 4.3 Template Syntax

Handlebars-inspired. Simple enough to learn in 2 minutes. No executable code.

#### Variables (HTML-escaped)

```html
<h1>{{site_title}}</h1>
<p>by {{owner_name}}</p>
<body style="background-color: {{bg_color}}; color: {{text_color}};">
```

#### Raw Variables (unescaped — for HTML content)

```html
<div class="content">
  {{{content}}}
</div>
```

Use `{{{triple braces}}}` for content that's already HTML (like rendered Markdown or plugin HTML). Double braces `{{escape}}` HTML entities for safety.

#### Partials

```html
{{> header}}

<main>{{{content}}}</main>

{{> footer}}
```

`{{> name}}` includes `partials/name.html` from the theme. Plugin partials use `{{> plugin:plugin-name}}`.

#### Loops

```html
<ul>
{{#each nav_links}}
  <li><a href="{{url}}">{{title}}</a></li>
{{/each}}
</ul>
```

Inside `{{#each}}`, the loop variable's properties are directly accessible. For simple arrays, use `{{.}}` for the current item.

#### Conditionals

```html
{{#if show_guestbook}}
  <h2>📖 Sign my Guestbook!</h2>
  {{> guestbook}}
{{/if}}

{{#if show_sidebar}}
  <td width="25%">{{> sidebar}}</td>
{{else}}
  <!-- no sidebar -->
{{/if}}
```

Falsy values: `false`, `0`, `""`, `null`, empty array `[]`. Everything else is truthy.

### 4.4 How Layouts, Templates, and Partials Compose

```
LAYOUT (base.html)
│
├── {{> header}}                    ← PARTIAL: partials/header.html
│   └── uses {{site_title}}, {{owner_name}}
│
├── {{> nav}}                       ← PARTIAL: partials/nav.html
│   └── uses {{#each nav_links}}
│
├── {{{content}}}                   ← TEMPLATE output inserted here
│   │
│   └── TEMPLATE (e.g., home.html)
│       ├── uses {{variables}}
│       ├── can include {{> partials}}
│       └── receives {{{content}}} ← CONTENT from .md/.html file
│
├── {{#if show_sidebar}}
│   └── {{> sidebar}}              ← PARTIAL: partials/sidebar.html
│
└── {{> footer}}                    ← PARTIAL: partials/footer.html
    └── uses {{year}}, {{show_visitor_counter}}
```

**Rendering order (inside-out):**
1. **Content**: Load `.md` file → convert to HTML (or load `.html` as-is)
2. **Template**: Insert content into template's `{{{content}}}` slot, resolve template-level partials and variables
3. **Layout**: Insert template output into layout's `{{{content}}}` slot, resolve layout-level partials and variables
4. **Final pass**: Resolve any remaining variables, clean up

#### Example: base.html (layout)

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{site_title}}</title>
  <link rel="stylesheet" href="/style.css">
</head>
<body background="/stars-bg.gif" bgcolor="{{bg_color}}" text="{{text_color}}"
      link="#ff00ff" vlink="#ff88ff" alink="#ffff00">

  {{> header}}
  {{> nav}}

  <table width="100%" cellpadding="10" cellspacing="0" border="0">
    <tr>
      <td {{#if show_sidebar}}width="75%"{{/if}} valign="top">
        {{{content}}}
      </td>
      {{#if show_sidebar}}
      <td width="25%" valign="top">
        {{> sidebar}}
      </td>
      {{/if}}
    </tr>
  </table>

  {{> footer}}

  <script src="/theme.js"></script>
</body>
</html>
```

#### Example: home.html (template)

```html
<center>
  <img src="/under-construction.gif" alt="Under Construction">
  <h1><font size="+3">✨ Welcome to {{site_title}}! ✨</font></h1>
  <marquee behavior="alternate" scrollamount="3">{{bio}}</marquee>
  <br>
  <img src="/flames.gif" alt="">
  <img src="/divider-rainbow.gif" width="100%" alt="">
</center>

<h2>About Me</h2>
{{{content}}}

{{#if show_guestbook}}
<img src="/divider-rainbow.gif" width="100%" alt="">
<h2>📖 Guestbook</h2>
{{> guestbook}}
{{/if}}
```

#### Example: content/index.md (user content)

```markdown
Hi, I'm **Mhd**! Welcome to my little corner of the airwaves.

I carry this site with me everywhere. If you're reading this,
we're probably on the same bus or in the same cafe. Cool, right?

### Things I like

- Making things
- Coffee
- Old-school web design
- Carrying websites in my pocket
```

### 4.5 Build Output

The CLI bakes everything into flat static HTML. No templates remain — just pure HTML/CSS/JS/assets.

```
build/
├── config.json
└── public/
    ├── index.html              ← fully rendered homepage
    ├── about/
    │   └── index.html          ← fully rendered about page
    ├── games/
    │   └── index.html
    ├── links/
    │   └── index.html
    ├── 404.html                ← custom 404 if theme provides one
    ├── style.css               ← from theme assets
    ├── theme.js                ← from theme assets
    ├── flames.gif              ← from theme assets
    ├── stars-bg.gif
    ├── under-construction.gif
    ├── divider-rainbow.gif
    ├── assets/                 ← user's own images
    │   ├── me.jpg
    │   └── cat.gif
    └── plugins/                ← plugin frontend assets
        ├── guestbook-widget/
        │   ├── guestbook.css
        │   └── guestbook.js
        └── visitor-counter/
            ├── counter.css
            └── counter.js
```

### 4.6 Skipping Themes (Raw Mode)

No `wificities.json` (or `mode: "raw"`), no theme processing. Write your own HTML, the CLI packages it as-is.

---

## 5. Plugins

Plugins add features to a wificity. Two types:

- **Frontend plugins**: HTML/CSS/JS widgets. No recompilation. Call existing API endpoints.
- **Backend plugins**: New API endpoints written in C/C++. Require firmware recompilation (CLI handles it).

### 5.1 Plugin Structure

```
plugins/
├── guestbook-widget/              ← FRONTEND only
│   ├── plugin.json
│   ├── frontend/
│   │   ├── guestbook.html         ← HTML snippet (used as partial)
│   │   ├── guestbook.css
│   │   └── guestbook.js
│   └── assets/
│       └── guestbook-icon.gif
│
├── visitor-counter/               ← FRONTEND only
│   ├── plugin.json
│   └── frontend/
│       ├── counter.html
│       ├── counter.css
│       └── counter.js
│
├── polls/                         ← BACKEND + frontend
│   ├── plugin.json
│   ├── frontend/
│   │   ├── poll.html
│   │   ├── poll.css
│   │   └── poll.js
│   └── backend/
│       ├── polls.h
│       └── polls.cpp
│
└── shoutbox/                      ← BACKEND + frontend
    ├── plugin.json
    ├── frontend/
    │   ├── shoutbox.html
    │   ├── shoutbox.css
    │   └── shoutbox.js
    └── backend/
        ├── shoutbox.h
        └── shoutbox.cpp
```

### 5.2 plugin.json

**Frontend-only plugin:**
```json
{
  "name": "Guestbook Widget",
  "id": "guestbook-widget",
  "description": "A retro guestbook form + entry list. Uses the built-in /api/guestbook endpoint.",
  "author": "wificities",
  "version": "1.0.0",
  "type": "frontend",
  "frontend": {
    "html": "frontend/guestbook.html",
    "css": "frontend/guestbook.css",
    "js": "frontend/guestbook.js"
  },
  "assets": ["assets/guestbook-icon.gif"],
  "api_dependencies": ["guestbook"]
}
```

**Backend + frontend plugin:**
```json
{
  "name": "Polls",
  "id": "polls",
  "description": "Create polls, let visitors vote. Results shown in real-time.",
  "author": "wificities",
  "version": "1.0.0",
  "type": "backend",
  "frontend": {
    "html": "frontend/poll.html",
    "css": "frontend/poll.css",
    "js": "frontend/poll.js"
  },
  "backend": {
    "source": "backend/",
    "api_prefix": "/api/polls",
    "storage_file": "polls.json",
    "symbol": "polls_plugin"
  },
  "config": {
    "max_polls": {
      "type": "number",
      "description": "Maximum number of active polls",
      "default": 5
    },
    "allow_anonymous": {
      "type": "boolean",
      "description": "Allow voting without entering a name",
      "default": true
    }
  }
}
```

The `symbol` field is the name of the `WifiCitiesPlugin` struct in the C code. The CLI uses this to generate the plugin registry.

### 5.3 Frontend Plugins

Frontend plugins are just HTML/CSS/JS snippets that get included in the site.

**Installation:**
```bash
wificities plugin add guestbook-widget
```

**What happens:**
1. CLI copies `frontend/` and `assets/` into the project at `.wificities/plugins/guestbook-widget/`
2. Updates `wificities.json` to list the plugin
3. The plugin's HTML is now available as a partial: `{{> plugin:guestbook-widget}}`
4. During build, CSS/JS are copied to `build/public/plugins/guestbook-widget/` and `<link>`/`<script>` tags are auto-injected into the layout's `<head>` and before `</body>`

**Usage in templates:**
```html
<!-- In any template or partial -->
{{> plugin:guestbook-widget}}
```

**Usage in raw HTML (manual):**
```html
<link rel="stylesheet" href="/plugins/guestbook-widget/guestbook.css">
<script src="/plugins/guestbook-widget/guestbook.js"></script>

<!-- paste the HTML snippet wherever you want it -->
<div class="wc-guestbook">...</div>
```

### 5.4 Backend Plugins — The Plugin C API

Backend plugins extend the firmware with new API endpoints and server-side logic.

#### plugin_api.h (provided by firmware)

```c
#ifndef WIFICITIES_PLUGIN_API_H
#define WIFICITIES_PLUGIN_API_H

#include <ESPAsyncWebServer.h>
#include <ArduinoJson.h>

// ============================================================
// Forward declarations
// ============================================================
class PluginStorage;
class ScopedServer;

// ============================================================
// WifiCitiesPlugin — the main struct every backend plugin fills
// ============================================================

typedef struct {
    // --- Metadata ---
    const char* name;           // Plugin identifier (e.g., "polls")
    const char* version;        // Semver (e.g., "1.0.0")
    const char* api_prefix;     // URL prefix (e.g., "/api/polls")

    // --- Lifecycle ---
    // Called once on boot. storage = this plugin's persistent store.
    // config = this plugin's section from config.json (may be empty).
    void (*on_init)(PluginStorage* storage, JsonObject config);

    // Called before deep sleep or restart. Flush your state.
    // Optional — set to NULL if not needed.
    void (*on_shutdown)();

    // --- HTTP Routes ---
    // Register your HTTP endpoints. Use the ScopedServer — it automatically
    // prefixes all your routes with api_prefix, so you register relative paths.
    // e.g., server->on("/vote", ...) registers /api/polls/vote
    void (*register_routes)(ScopedServer* server, PluginStorage* storage);

    // --- WebSocket (optional, NULL to skip) ---
    // Path for WebSocket endpoint (e.g., "/ws/shoutbox").
    // Set to NULL if the plugin doesn't use WebSocket.
    const char* ws_path;

    // Called when a WebSocket message is received.
    // Only called if ws_path is not NULL.
    void (*on_ws_message)(AsyncWebSocketClient* client, const char* message);

    // --- Event Hooks (all optional, NULL to skip) ---
    void (*on_client_connect)(const char* mac);
    void (*on_client_disconnect)(const char* mac);

} WifiCitiesPlugin;

// ============================================================
// ScopedServer — route registration scoped to a prefix
// ============================================================
//
// Wraps AsyncWebServer and enforces that a plugin can ONLY
// register routes under its own api_prefix. Prevents plugins
// from hijacking core routes or other plugins' routes.
//
// When you call server->on("/vote", ...), it actually registers
// /api/polls/vote (prefix + your path).

class ScopedServer {
public:
    ScopedServer(AsyncWebServer* server, const char* prefix);

    // Register a route (path is relative to your prefix)
    void on(const char* relativePath,
            WebRequestMethodComposite method,
            ArRequestHandlerFunction onRequest);

    // Register a route with body handler
    void on(const char* relativePath,
            WebRequestMethodComposite method,
            ArRequestHandlerFunction onRequest,
            ArUploadHandlerFunction onUpload,
            ArBodyHandlerFunction onBody);

private:
    AsyncWebServer* _server;
    String _prefix;
};

// ============================================================
// PluginStorage — persistent JSON storage per plugin
// ============================================================
//
// Each plugin gets its own file in /data/<plugin-name>.json.
// Reads/writes go through this class. Auto-flushed periodically
// (every 5 minutes) and on shutdown. Call flush() to force.

class PluginStorage {
public:
    PluginStorage(const char* pluginName);

    // Full document access
    JsonDocument read();
    bool write(const JsonDocument& doc);

    // Key-value convenience methods
    String getString(const char* key, const char* defaultValue = "");
    int getInt(const char* key, int defaultValue = 0);
    bool getBool(const char* key, bool defaultValue = false);
    void set(const char* key, const char* value);
    void set(const char* key, int value);
    void set(const char* key, bool value);

    // Force write to disk (normally auto-flushed)
    void flush();

    // Info
    size_t fileSize();          // Current file size in bytes
    const char* filePath();     // e.g., "/data/polls.json"
};

#endif // WIFICITIES_PLUGIN_API_H
```

#### Key design decisions

1. **ScopedServer** enforces route isolation. A plugin registered with prefix `/api/polls` can only add routes under `/api/polls/*`. It physically cannot hijack `/api/guestbook` or `/admin` or `/`. This is enforced at the API level, not by convention.

2. **PluginStorage** provides a simple JSON file per plugin. Plugins never touch each other's storage. The firmware handles flush timing to reduce flash wear.

3. **on_init receives config** so plugins can read their settings from `config.json` without knowing the file structure.

4. **WebSocket support** is optional. Plugins set `ws_path` and `on_ws_message` if they need real-time features (like a shoutbox/chat). For most plugins, polling is fine — just use HTTP routes.

5. **Event hooks** let plugins react to device connections/disconnections. A "who's here" plugin could show currently connected devices, for example.

#### Example: Polls Plugin

```cpp
// plugins/polls/backend/polls.cpp
#include "plugin_api.h"

static PluginStorage* _storage = nullptr;
static int _maxPolls = 5;

// ---- Lifecycle ----

void polls_init(PluginStorage* storage, JsonObject config) {
    _storage = storage;
    _maxPolls = config["max_polls"] | 5;

    // Initialize storage if empty
    JsonDocument doc = storage->read();
    if (doc.isNull()) {
        doc.to<JsonObject>();
        doc["polls"] = doc.createNestedArray("polls");
        storage->write(doc);
    }
}

// ---- Routes ----

void polls_register_routes(ScopedServer* server, PluginStorage* storage) {

    // GET /api/polls → list all polls with results
    server->on("/", HTTP_GET,
        [](AsyncWebServerRequest* req) {
            JsonDocument doc = _storage->read();
            String out;
            serializeJson(doc["polls"], out);
            req->send(200, "application/json", out);
        }
    );

    // POST /api/polls → create a new poll (admin only)
    server->on("/", HTTP_POST,
        [](AsyncWebServerRequest* req) {},
        NULL,
        [](AsyncWebServerRequest* req, uint8_t* data, size_t len,
           size_t index, size_t total) {
            JsonDocument body;
            deserializeJson(body, (char*)data);

            // TODO: check admin password
            // TODO: check max polls limit
            // TODO: add poll to storage

            req->send(201, "application/json", "{\"ok\":true}");
        }
    );

    // POST /api/polls/vote → vote on a poll option
    server->on("/vote", HTTP_POST,
        [](AsyncWebServerRequest* req) {},
        NULL,
        [](AsyncWebServerRequest* req, uint8_t* data, size_t len,
           size_t index, size_t total) {
            JsonDocument body;
            deserializeJson(body, (char*)data);

            int pollId = body["poll_id"];
            int optionId = body["option_id"];

            JsonDocument doc = _storage->read();
            // increment vote count for the option...
            _storage->write(doc);

            req->send(200, "application/json", "{\"ok\":true}");
        }
    );
}

// ---- Registration ----

WifiCitiesPlugin polls_plugin = {
    .name            = "polls",
    .version         = "1.0.0",
    .api_prefix      = "/api/polls",
    .on_init         = polls_init,
    .on_shutdown     = NULL,
    .register_routes = polls_register_routes,
    .ws_path         = NULL,
    .on_ws_message   = NULL,
    .on_client_connect    = NULL,
    .on_client_disconnect = NULL,
};
```

#### Plugin compilation flow

1. `wificities plugin add polls`
2. CLI detects `type: "backend"` in `plugin.json`
3. CLI copies `backend/polls.h` and `backend/polls.cpp` to `firmware/lib/plugins/polls/`
4. CLI regenerates `firmware/lib/plugins/plugin_registry.h`:

```c
// AUTO-GENERATED by wificities CLI — do not edit manually
#ifndef PLUGIN_REGISTRY_H
#define PLUGIN_REGISTRY_H

#include "plugin_api.h"

// Plugin extern declarations (defined in their respective .cpp files)
extern WifiCitiesPlugin polls_plugin;
extern WifiCitiesPlugin shoutbox_plugin;

// Plugin registry array
static WifiCitiesPlugin* registered_plugins[] = {
    &polls_plugin,
    &shoutbox_plugin,
};

static const int PLUGIN_COUNT = 2;

#endif // PLUGIN_REGISTRY_H
```

5. On `wificities build`, firmware is recompiled with PlatformIO (includes new plugin source)
6. On `wificities flash`, updated firmware + filesystem are flashed

#### Firmware boot sequence (plugin loading)

```cpp
// In main.cpp
#include "plugin_registry.h"

AsyncWebServer server(80);

void setup() {
    // ... LittleFS init, config load, WiFi AP, DNS, captive portal ...
    // ... built-in API routes (/api/guestbook, /api/visitors, /api/info) ...
    // ... admin routes (/admin) ...

    // Load plugins
    JsonDocument configDoc;
    // (already loaded config.json into configDoc)

    for (int i = 0; i < PLUGIN_COUNT; i++) {
        WifiCitiesPlugin* plugin = registered_plugins[i];

        // Create scoped server for this plugin
        ScopedServer* scoped = new ScopedServer(&server, plugin->api_prefix);

        // Create storage for this plugin
        PluginStorage* storage = new PluginStorage(plugin->name);

        // Get plugin config section (or empty object)
        JsonObject pluginConfig = configDoc["plugins"][plugin->name]
            .as<JsonObject>();

        // Register routes (scoped to plugin's prefix)
        plugin->register_routes(scoped, storage);

        // Register WebSocket if plugin uses it
        if (plugin->ws_path != NULL && plugin->on_ws_message != NULL) {
            // ... set up AsyncWebSocket on plugin->ws_path ...
        }

        // Call init
        if (plugin->on_init) {
            plugin->on_init(storage, pluginConfig);
        }
    }

    // Static file server (catch-all, lowest priority)
    // ... folder-based routing handler ...

    server.begin();
}
```

### 5.5 Plugin Summary

| | Frontend Plugin | Backend Plugin |
|---|---|---|
| **Contains** | HTML/CSS/JS | HTML/CSS/JS + C/C++ source |
| **Adds** | UI widgets | New API endpoints + UI widgets |
| **Recompile needed** | No | Yes (CLI handles it) |
| **PlatformIO needed** | No | Yes |
| **Storage** | Uses existing APIs (guestbook, visitors) | Gets own JSON file in `/data/` |
| **Route isolation** | N/A | Enforced by ScopedServer |
| **Examples** | guestbook widget, visitor counter, clock, music player | polls, shoutbox, file drop, chat, reaction buttons |
| **User experience** | `plugin add` → done | `plugin add` → `build` → `flash` |

### 5.6 Plugin Sources

```bash
# Built-in (ships with wificities)
wificities plugin add guestbook-widget

# Community (from git)
wificities plugin add https://github.com/someone/wificities-plugin-reactions

# Local (for development)
wificities plugin add ./my-custom-plugin
```

Installed plugins are tracked in `wificities.json` and cached locally in `.wificities/plugins/`.

---

## 6. CLI Tool

Python CLI built with Click. The main interface for creating, building, and flashing wificities.

### 6.1 Installation

```bash
pip install wificities
```

Dependencies:
- `click` — CLI framework
- `mistune` — Markdown to HTML conversion
- `esptool` — ESP32 flashing
- `littlefs-python` — LittleFS image creation
- `watchdog` — file watching for dev server hot reload

PlatformIO is **not** a dependency. It's only needed if the user has backend plugins. The CLI will prompt to install it when needed.

### 6.2 Commands

#### `wificities init [name]`

Create a new wificity project.

```bash
wificities init my-site                          # interactive — asks everything
wificities init my-site --theme geocities-flame   # skip theme picker
wificities init my-site --raw                     # raw HTML, no theme
```

**Interactive flow:**
```
$ wificities init my-site

🏙️  Welcome to WifiCities!

? What's your wificity called? > Mhd's Place
? What SSID should it broadcast? > ✨ Mhd's Place ✨
? Set an admin password: > ********
? Pick a theme:
  ❯ geocities-flame  — Under construction since 1999
    retro-terminal   — Green phosphor CRT vibes
    y2k-cyber        — Millennium bug aesthetic
    (none)           — Raw HTML, I'll build my own

[geocities-flame selected]

? Your name or handle: > Mhd
? A short bio: > Welcome to my corner of the airwaves!
? Background color [#000033]: >
? Text color [#00ff00]: >

✅ Created my-site/
   config.json
   wificities.json
   content/index.md
   content/about.md

Next steps:
  cd my-site
  wificities serve        # preview locally
  wificities build        # build for ESP32
  wificities flash        # flash to ESP32
```

**Generated project (theme mode):**
```
my-site/
├── config.json
├── wificities.json
└── content/
    ├── index.md
    └── about.md
```

**Generated project (raw mode):**
```
my-site/
├── config.json
└── public/
    └── index.html
```

#### `wificities serve`

Local development server with hot reload and mock APIs.

```bash
wificities serve                  # default port 8080
wificities serve --port 3000      # custom port
```

**What it does:**
- Runs a local HTTP server on `localhost:8080`
- **Theme mode**: Renders templates on every request (no manual rebuild needed). Edit a `.md` file → refresh browser → see changes.
- **Raw mode**: Serves `public/` directly
- **Mock APIs**: Simulates all firmware API endpoints in-memory:
  - `/api/guestbook` — entries stored in memory (lost on restart)
  - `/api/visitors` — fake counter
  - `/api/info` — mock system info
  - Plugin API endpoints — if backend plugin provides a `mock.py` file, it's loaded
- **Hot reload**: Injects a small `<script>` that polls for file changes. When a file changes, browser reloads automatically. The injected script is stripped during `build`.
- **Captive portal simulation**: Visiting `localhost:8080/__captive` simulates the captive portal detection flow for testing

#### `wificities build`

Build the site into flashable output.

```bash
wificities build                    # build everything
wificities build --size-report      # show detailed size breakdown
```

**Build pipeline:**

1. **Detect mode**: Check for `wificities.json` → theme mode or raw mode
2. **Theme mode**:
   a. Load theme (from `themes/` in the wificities install, or a local path)
   b. For each page in `wificities.json`:
      - Load content file (`.md` → Markdown-to-HTML via mistune, or `.html` as-is)
      - Resolve template: inject content into template's `{{{content}}}` slot
      - Resolve layout: inject template output into layout's `{{{content}}}` slot
      - Resolve all partials (`{{> name}}`, `{{> plugin:name}}`)
      - Resolve all variables (page → global → theme defaults → built-ins)
      - Resolve loops (`{{#each}}`) and conditionals (`{{#if}}`)
      - Write to `build/public/<url-path>/index.html`
   c. Copy theme assets to `build/public/`
   d. Copy user assets (`content/assets/`) to `build/public/assets/`
3. **Raw mode**: Copy `public/` to `build/public/`
4. **Plugins** (both modes):
   - Copy frontend plugin assets to `build/public/plugins/<name>/`
   - In theme mode: plugin CSS/JS references auto-injected into layout HTML
5. Copy `config.json` to `build/config.json`
6. Create empty `build/data/` directory (firmware creates files here at runtime)
7. **Validate**:
   - `config.json` is valid JSON with required fields
   - `build/public/index.html` exists
   - No broken internal links (href/src pointing to missing files)
   - Total size check against LittleFS capacity
8. **Backend plugins**: If any backend plugins are installed, compile firmware with PlatformIO
9. **Create LittleFS image** from `build/` directory
10. **Print summary**:

```
✅ Build complete!

  Pages:      4
  Plugins:    2 (frontend: 2, backend: 0)
  Total size: 847 KB / 2,500 KB (33%)
  Firmware:   pre-built (no backend plugins)

  Output: build/
```

**Size report** (`--size-report`):
```
📊 Size Breakdown:

  public/index.html              12 KB
  public/about/index.html         8 KB
  public/games/index.html         6 KB
  public/links/index.html         5 KB
  public/style.css               14 KB
  public/theme.js                 3 KB
  public/images/                348 KB
    ├── flames.gif               24 KB
    ├── stars-bg.gif             12 KB
    ├── under-construction.gif    8 KB
    └── ... (8 more files)      304 KB
  public/plugins/               112 KB
  config.json                     1 KB
  ──────────────────────────────────
  TOTAL                         509 KB / 2,500 KB (20%)
  REMAINING                   1,991 KB (for runtime data: guestbook, visitors, plugins)
```

#### `wificities flash`

Flash firmware + filesystem to an ESP32.

```bash
wificities flash                            # auto-detect board and port
wificities flash --port /dev/ttyUSB0        # specify USB port
wificities flash --board esp32s3            # specify board variant
wificities flash --only firmware            # flash only firmware (skip filesystem)
wificities flash --only filesystem          # flash only filesystem (skip firmware — faster!)
```

**How it works:**
1. Auto-detect connected ESP32 (via `esptool.py chip_id`) or use specified `--board`
2. If no backend plugins: use **pre-built firmware binary** (no PlatformIO needed!)
3. If backend plugins: use firmware compiled during `build` step
4. Create LittleFS image from `build/` using `mklittlefs`/`littlefs-python`
5. Flash firmware binary to app partition using `esptool.py`
6. Flash LittleFS image to data partition using `esptool.py`
7. Reset ESP32

**Pre-built firmware binaries:**

For users without backend plugins, the CLI ships with pre-compiled firmware binaries:
- `firmware-esp32.bin`
- `firmware-esp32s2.bin`
- `firmware-esp32s3.bin`
- `firmware-esp32c3.bin`

These are compiled from the core firmware (no plugins) and bundled with the Python package. This means **most users never need PlatformIO**. Only backend plugin users need it.

**The `--only filesystem` option:**

If you're just changing site content (HTML, CSS, images, config) and haven't added/removed backend plugins, you only need to reflash the filesystem partition. This is **much faster** (~5 seconds vs ~30 seconds for full flash). The CLI detects when a firmware reflash is unnecessary and suggests this option.

```
$ wificities flash

ℹ️  No firmware changes detected. Use --only filesystem for faster flashing.

Flashing filesystem to /dev/ttyUSB0...
  [████████████████████████████] 100%

✅ Done! Your wificity is broadcasting: ✨ Mhd's Place ✨
```

#### `wificities theme list`

```bash
$ wificities theme list

Available themes:

  geocities-flame    Under construction since 1999. Flames, stars, beveled everything.
  retro-terminal     Green phosphor CRT vibes. Monospace everything.
  y2k-cyber          Millennium bug aesthetic. Chrome gradients and matrix rain.
```

#### `wificities theme preview <name>`

```bash
wificities theme preview geocities-flame
# Opens localhost:8080 with the theme rendered with demo content
```

#### `wificities plugin list`

```bash
$ wificities plugin list

Built-in plugins:

  FRONTEND
  guestbook-widget     Retro guestbook form + entries list
  visitor-counter      Hit counter with retro digit sprites
  clock-widget         Animated clock widget
  music-player         MIDI-style background music player

  BACKEND
  polls                Create polls, let visitors vote
  shoutbox             Real-time message board (WebSocket)

Installed in this project:
  guestbook-widget   1.0.0   (frontend)
  visitor-counter    1.0.0   (frontend)
```

#### `wificities plugin add <name|url|path>`

```bash
wificities plugin add guestbook-widget                              # built-in
wificities plugin add https://github.com/user/wificities-plugin-x   # community
wificities plugin add ./my-plugin                                    # local
```

#### `wificities plugin remove <name>`

```bash
wificities plugin remove polls
# Removes backend source, frontend assets, updates registry, updates wificities.json
```

#### `wificities validate`

Check the project for issues without building.

```bash
$ wificities validate

✅ config.json valid
✅ wificities.json valid
✅ All content files exist
✅ All templates referenced exist in theme
⚠️  Total estimated size: 2,200 KB / 2,500 KB (88%) — getting tight!
❌ Broken link in content/about.md: /images/old-photo.jpg (file not found)

1 error, 1 warning
```

---

## 7. Storage & Partitions

### 7.1 Custom Partition Table

Default ESP32 (4MB flash) partition tables waste space on OTA. We use a custom single-app partition to maximize filesystem space:

```csv
# Name,    Type, SubType, Offset,   Size,      Flags
nvs,       data, nvs,     0x9000,   0x5000,
otadata,   data, ota,     0xe000,   0x2000,
app0,      app,  ota_0,   0x10000,  0x180000,
littlefs,  data, spiffs,  0x190000, 0x270000,
```

| Partition | Size | Purpose |
|-----------|------|---------|
| `nvs` | 20 KB | Non-volatile storage (WiFi credentials, etc.) |
| `otadata` | 8 KB | OTA metadata |
| `app0` | 1.5 MB | Firmware (core + plugins). Generous for growth. |
| `littlefs` | 2.4375 MB | **User site + data**. This is where everything lives. |

**Note**: For ESP32-S3 boards with 8MB or 16MB flash, the partition table is adjusted to give even more filesystem space (up to ~14MB on a 16MB board).

### 7.2 LittleFS Layout on ESP32

```
/
├── config.json                    ← runtime config
├── data/
│   ├── guestbook.json             ← guestbook entries
│   ├── visitors.json              ← visitor count
│   ├── polls.json                 ← plugin storage (if installed)
│   └── shoutbox.json              ← plugin storage (if installed)
└── public/
    ├── index.html                 ← / (captive portal entry)
    ├── about/
    │   └── index.html             ← /about
    ├── style.css
    ├── images/
    │   └── ...
    └── plugins/
        └── guestbook-widget/
            ├── guestbook.css
            └── guestbook.js
```

### 7.3 Flash Wear Management

LittleFS has built-in wear leveling, but frequent writes still reduce flash lifespan. Strategy:

| Data | Write frequency | Approach |
|------|----------------|----------|
| Guestbook entries | Rare (human-speed) | Write immediately on each POST |
| Visitor count | Every new connection | **Buffer in RAM**, flush to disk every 10 increments OR every 5 minutes, whichever comes first |
| Plugin storage | Varies | Auto-flush every 5 minutes. Plugins can call `flush()` to force. |

On clean shutdown (restart command from admin), all buffered data is flushed.

---

## 8. Project Repository Structure

```
wificities/
├── project.md                     ← this file
│
├── firmware/                      ← ESP32 firmware (PlatformIO)
│   ├── platformio.ini             ← multi-board config
│   ├── partitions.csv             ← custom partition table
│   ├── src/
│   │   └── main.cpp               ← core firmware
│   └── lib/
│       ├── captive_portal/        ← DNS server + captive portal detection
│       │   ├── captive_portal.h
│       │   └── captive_portal.cpp
│       ├── file_server/           ← folder-based routing static server
│       │   ├── file_server.h
│       │   └── file_server.cpp
│       ├── api/                   ← built-in REST APIs
│       │   ├── api.h
│       │   ├── guestbook_api.cpp
│       │   ├── visitors_api.cpp
│       │   └── info_api.cpp
│       ├── admin/                 ← admin panel
│       │   ├── admin.h
│       │   ├── admin.cpp
│       │   └── admin_page.h       ← embedded HTML for /admin
│       ├── plugin_api/            ← Plugin C API
│       │   ├── plugin_api.h       ← the interface plugins implement
│       │   ├── plugin_storage.cpp ← PluginStorage implementation
│       │   └── scoped_server.cpp  ← ScopedServer implementation
│       └── plugins/               ← backend plugin source (auto-managed by CLI)
│           └── plugin_registry.h  ← auto-generated list of installed plugins
│
├── cli/                           ← Python CLI
│   ├── pyproject.toml
│   ├── wificities/
│   │   ├── __init__.py
│   │   ├── cli.py                 ← Click entry point + command registration
│   │   ├── init.py                ← wificities init
│   │   ├── build.py               ← template engine + build pipeline
│   │   ├── flash.py               ← firmware compilation + esptool flashing
│   │   ├── serve.py               ← local dev server + mock APIs + hot reload
│   │   ├── plugins.py             ← plugin add/remove/list
│   │   ├── themes.py              ← theme list/preview
│   │   ├── validate.py            ← project validation
│   │   ├── template_engine.py     ← Handlebars-like template processor
│   │   └── firmware_bins/         ← pre-built firmware binaries
│   │       ├── esp32.bin
│   │       ├── esp32s2.bin
│   │       ├── esp32s3.bin
│   │       └── esp32c3.bin
│   └── tests/
│       ├── test_template_engine.py
│       ├── test_build.py
│       └── test_validate.py
│
├── themes/
│   ├── geocities-flame/
│   │   ├── theme.json
│   │   ├── layouts/
│   │   ├── templates/
│   │   ├── partials/
│   │   ├── assets/
│   │   └── preview.png
│   ├── retro-terminal/
│   └── y2k-cyber/
│
├── plugins/
│   ├── guestbook-widget/          ← frontend
│   ├── visitor-counter/           ← frontend
│   ├── clock-widget/              ← frontend
│   ├── music-player/              ← frontend
│   ├── polls/                     ← backend + frontend
│   └── shoutbox/                  ← backend + frontend
│
└── docs/
    ├── getting-started.md
    ├── making-themes.md
    ├── making-plugins.md
    └── plugin-api-reference.md
```

---

## 9. Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Firmware | C++ / Arduino framework | Widest ESP32 board support, huge community |
| Build system | PlatformIO | Multi-board support, dependency management, toolchain handling |
| Web server | ESPAsyncWebServer | Async, handles multiple concurrent connections, WebSocket support |
| JSON | ArduinoJson | De facto standard for JSON on Arduino, efficient memory use |
| Filesystem | LittleFS | Wear leveling, reliable, power-loss safe, good for small files |
| DNS | Custom lightweight | ~50 lines of code, resolves everything to AP IP |
| CLI | Python 3.9+ / Click | Cross-platform, easy to install, good CLI UX |
| Markdown | mistune | Fast, lightweight, zero dependencies, CommonMark-ish |
| Flashing | esptool.py | Official Espressif tool, Python-native, reliable |
| LittleFS images | littlefs-python or mklittlefs | Create flashable filesystem images |
| Hot reload | watchdog | File system monitoring for dev server |

### 9.1 PlatformIO Configuration

```ini
[platformio]
default_envs = esp32

[env]
framework = arduino
monitor_speed = 115200
board_build.filesystem = littlefs
board_build.partitions = partitions.csv
lib_deps =
    esphome/ESPAsyncWebServer-esphome@^3.1.0
    bblanchon/ArduinoJson@^7.0.0

[env:esp32]
platform = espressif32
board = esp32dev

[env:esp32s2]
platform = espressif32
board = esp32-s2-saola-1

[env:esp32s3]
platform = espressif32
board = esp32-s3-devkitc-1

[env:esp32c3]
platform = espressif32
board = esp32-c3-devkitm-1
```

---

## 10. Security

| Threat | Mitigation |
|--------|-----------|
| **Guestbook spam** | Rate limiting: 1 entry per MAC per 60s. Max entry length. Max total entries. |
| **XSS via guestbook** | Firmware strips `<` and `>` from name and message on POST (input sanitization). Frontend plugins should also escape when rendering — defense in depth. |
| **Admin access** | Admin password required for all destructive operations. Stored in `config.json` on device. |
| **Path traversal** (`../../etc/passwd`) | ESPAsyncWebServer normalizes paths. Firmware also validates that resolved path starts with `/public/`. |
| **Storage exhaustion** | Max entries enforced per API. `/api/info` reports free space. Firmware returns 507 when full. |
| **Plugin route hijack** | ScopedServer enforces prefix isolation — plugins cannot register routes outside their prefix. |
| **WiFi deauth attacks** | Not mitigable at the ESP32 level. Inherent to open WiFi. Documented as a known limitation. |
| **No HTTPS** | Intentional. Captive portals can't use HTTPS (no trusted CA on a local network). Traffic is local-only and ephemeral — acceptable tradeoff. |

---

## 11. User Flows

### First-time user (beginner)

```bash
pip install wificities
wificities init my-site --theme geocities-flame
cd my-site
# edit content/index.md with any text editor
wificities serve            # preview at localhost:8080
wificities build            # compile site
wificities flash            # flash to ESP32
# done — ESP32 is now broadcasting your wificity
```

**Total commands: 5. Time to first broadcast: ~5 minutes.**

### Power user (raw HTML)

```bash
wificities init my-site --raw
cd my-site
# write public/index.html, style.css, etc. from scratch
wificities plugin add guestbook-widget
wificities serve
wificities build
wificities flash
```

### Content update (no firmware change)

```bash
# edit content/about.md
wificities build
wificities flash --only filesystem    # ~5 seconds, only reflashes site files
```

### Adding a backend plugin

```bash
wificities plugin add polls
wificities build                      # recompiles firmware (needs PlatformIO)
wificities flash                      # full flash (firmware + filesystem)
```

### Theme developer

```bash
mkdir my-theme && cd my-theme
# create theme.json, layouts/, templates/, partials/, assets/
cd /path/to/test-site
wificities init test --theme /path/to/my-theme
wificities serve          # iterate
```

### Plugin developer

```bash
mkdir my-plugin && cd my-plugin
# create plugin.json, frontend/ (and optionally backend/)
cd /path/to/test-site
wificities plugin add /path/to/my-plugin
wificities serve          # test
```

---

## 12. Future Ideas (Not MVP)

- **Discovery**: ESP32s could detect nearby wificities via WiFi scanning and show a "neighbors" page
- **Trading cards**: Visitors get a unique collectible card/badge for each wificity they visit (stored in browser localStorage)
- **Pre-built kits**: Sell ready-to-go ESP32s with custom PCBs, cute cases, and a starter theme pre-flashed
- **Web-based editor**: A local Electron/web app for building sites visually with drag & drop skeuomorphic widgets
- **OTA updates**: Update site content over WiFi without USB cable (using the admin panel)
- **Mesh mode**: Multiple ESP32s linking their wificities together — visit one, see links to nearby others
- **Plugin marketplace**: `wificities plugin search` with a curated registry
- **Analytics page**: Built into admin — see visitor patterns, popular pages, peak times

---

## 13. MVP Scope

### Must have

- [ ] **Firmware**: WiFi AP + DNS server + captive portal (all major OS support)
- [ ] **Firmware**: Static file server with folder-based routing
- [ ] **Firmware**: `/api/guestbook` (GET, POST, DELETE) with rate limiting + input sanitization
- [ ] **Firmware**: `/api/visitors` (GET) with buffered writes
- [ ] **Firmware**: `/api/info` (GET)
- [ ] **Firmware**: Built-in `/admin` panel
- [ ] **Firmware**: `config.json` reader with sensible defaults on missing/corrupt config
- [ ] **Firmware**: Plugin C API (ScopedServer + PluginStorage + plugin registry loader)
- [ ] **Firmware**: Custom partition table (maximize LittleFS)
- [ ] **Firmware**: Multi-board support (ESP32, S2, S3, C3)
- [ ] **CLI**: `wificities init` (interactive, theme mode + raw mode)
- [ ] **CLI**: `wificities build` (template engine + build pipeline + size validation)
- [ ] **CLI**: `wificities flash` (pre-built binaries + esptool + `--only filesystem`)
- [ ] **CLI**: `wificities serve` (dev server + mock APIs + hot reload)
- [ ] **CLI**: `wificities plugin add/remove/list`
- [ ] **CLI**: `wificities theme list`
- [ ] **CLI**: `wificities validate`
- [ ] **Template engine**: Variables (`{{}}`), raw (`{{{}}}`), partials (`{{> }}`), loops (`{{#each}}`), conditionals (`{{#if}}`)
- [ ] **Theme**: `geocities-flame` (complete with layouts, templates, partials, full retro aesthetic)
- [ ] **Plugin**: `guestbook-widget` (frontend)
- [ ] **Plugin**: `visitor-counter` (frontend)
- [ ] **Pre-built firmware binaries** for ESP32, S2, S3, C3

### Nice to have (post-MVP)

- [ ] Backend plugin: `polls`
- [ ] Backend plugin: `shoutbox` (with WebSocket)
- [ ] Theme: `retro-terminal`
- [ ] Theme: `y2k-cyber`
- [ ] Plugin: `clock-widget`
- [ ] Plugin: `music-player`
- [ ] `wificities theme preview`
- [ ] Community plugin install from git URL
- [ ] mDNS (`wificity.local`)
- [ ] Size report (`--size-report`)
- [ ] Asset optimization warnings

---

## 14. License

Open source. MIT or GPLv3 — to be decided.

MIT is more permissive (anyone can use it however they want, including in commercial kits). GPLv3 forces derivatives to stay open source. Given the community-first ethos and future kit sales, **MIT** is recommended — it maximizes adoption and doesn't block commercial use by us or anyone else.
