#ifndef WIFICITIES_PLUGIN_API_H
#define WIFICITIES_PLUGIN_API_H

#include <ESPAsyncWebServer.h>
#include <ArduinoJson.h>
#include <LittleFS.h>

// ============================================================
// ScopedServer — route registration scoped to a prefix
// ============================================================
//
// Wraps AsyncWebServer so plugins can only register routes under
// their own API prefix. Prevents plugins from hijacking core
// routes or other plugins' routes.

class ScopedServer {
public:
    ScopedServer(AsyncWebServer* server, const char* prefix)
        : _server(server), _prefix(prefix) {}

    void on(const char* relativePath, WebRequestMethodComposite method,
            ArRequestHandlerFunction onRequest) {
        String fullPath = _prefix + String(relativePath);
        _server->on(fullPath.c_str(), method, onRequest);
    }

    void on(const char* relativePath, WebRequestMethodComposite method,
            ArRequestHandlerFunction onRequest,
            ArUploadHandlerFunction onUpload,
            ArBodyHandlerFunction onBody) {
        String fullPath = _prefix + String(relativePath);
        _server->on(fullPath.c_str(), method, onRequest, onUpload, onBody);
    }

private:
    AsyncWebServer* _server;
    String _prefix;
};

// ============================================================
// PluginStorage — persistent JSON storage per plugin
// ============================================================

class PluginStorage {
public:
    PluginStorage(const char* pluginName) {
        _path = "/data/" + String(pluginName) + ".json";
        _dirty = false;
        _lastFlush = millis();

        if (!LittleFS.exists("/data")) {
            LittleFS.mkdir("/data");
        }
    }

    JsonDocument read() {
        JsonDocument doc;
        if (LittleFS.exists(_path)) {
            File f = LittleFS.open(_path, "r");
            if (f) {
                deserializeJson(doc, f);
                f.close();
            }
        }
        return doc;
    }

    bool write(const JsonDocument& doc) {
        File f = LittleFS.open(_path, "w");
        if (!f) return false;
        serializeJson(doc, f);
        f.close();
        _dirty = false;
        _lastFlush = millis();
        return true;
    }

    String getString(const char* key, const char* defaultValue = "") {
        JsonDocument doc = read();
        return doc[key] | defaultValue;
    }

    int getInt(const char* key, int defaultValue = 0) {
        JsonDocument doc = read();
        return doc[key] | defaultValue;
    }

    bool getBool(const char* key, bool defaultValue = false) {
        JsonDocument doc = read();
        return doc[key] | defaultValue;
    }

    void set(const char* key, const char* value) {
        JsonDocument doc = read();
        doc[key] = value;
        write(doc);
    }

    void set(const char* key, int value) {
        JsonDocument doc = read();
        doc[key] = value;
        write(doc);
    }

    void set(const char* key, bool value) {
        JsonDocument doc = read();
        doc[key] = value;
        write(doc);
    }

    void flush() { _dirty = false; _lastFlush = millis(); }

    // Auto-flush check — call from loop()
    void autoFlush() {
        if (_dirty && millis() - _lastFlush > 300000) {
            flush();
        }
    }

    size_t fileSize() {
        if (!LittleFS.exists(_path)) return 0;
        File f = LittleFS.open(_path, "r");
        size_t s = f ? f.size() : 0;
        if (f) f.close();
        return s;
    }

    const char* filePath() { return _path.c_str(); }

private:
    String _path;
    bool _dirty;
    unsigned long _lastFlush;
};

// ============================================================
// WifiCitiesPlugin — main plugin struct
// ============================================================

typedef struct {
    // Metadata
    const char* name;
    const char* version;
    const char* api_prefix;

    // Lifecycle
    void (*on_init)(PluginStorage* storage, JsonObject config);
    void (*on_shutdown)();

    // HTTP routes (ScopedServer enforces prefix isolation)
    void (*register_routes)(ScopedServer* server, PluginStorage* storage);

    // WebSocket (optional — set both to NULL if unused)
    const char* ws_path;
    void (*on_ws_message)(AsyncWebSocketClient* client, const char* message);

    // Event hooks (optional — NULL to skip)
    void (*on_client_connect)(const char* mac);
    void (*on_client_disconnect)(const char* mac);

} WifiCitiesPlugin;

#endif // WIFICITIES_PLUGIN_API_H
