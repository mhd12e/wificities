#ifndef WIFICITIES_API_H
#define WIFICITIES_API_H

#include <ESPAsyncWebServer.h>
#include <ArduinoJson.h>
#include <LittleFS.h>

// ============================================================
// Guestbook API
// ============================================================

class GuestbookAPI {
public:
    GuestbookAPI();

    void begin(int maxEntries, int maxNameLen, int maxMsgLen, int rateLimitSec);
    void registerRoutes(AsyncWebServer* server);

private:
    int _maxEntries;
    int _maxNameLen;
    int _maxMsgLen;
    int _rateLimitSec;
    static const char* DATA_PATH;

    // Rate limiting: MAC -> last post timestamp
    struct RateEntry {
        uint8_t mac[6];
        unsigned long lastPost;
    };
    static const int MAX_RATE_ENTRIES = 32;
    RateEntry _rateTable[MAX_RATE_ENTRIES];
    int _rateCount;

    bool _isRateLimited(const String& remoteIP);
    void _recordPost(const String& remoteIP);

    JsonDocument _readEntries();
    void _writeEntries(const JsonDocument& doc);

    // Sanitize input: strip < and > to prevent XSS
    static String _sanitize(const String& input, int maxLen);

    // Get next ID
    int _nextId(const JsonDocument& doc);
};

// ============================================================
// Visitors API
// ============================================================

class VisitorsAPI {
public:
    VisitorsAPI();

    void begin();
    void registerRoutes(AsyncWebServer* server);

    // Call when a client connects/disconnects
    void onClientConnect();
    void onClientDisconnect();

    // Call periodically from loop() to flush buffered writes
    void loop();

private:
    static const char* DATA_PATH;

    int _total;
    int _current;
    int _unflushed;          // writes since last flush
    unsigned long _lastFlush;

    void _load();
    void _flush();

};

// ============================================================
// Info API
// ============================================================

class InfoAPI {
public:
    InfoAPI();

    void begin(const String& siteName, const String& ssid,
               const char* fwVersion);
    void registerRoutes(AsyncWebServer* server, VisitorsAPI* visitors);

private:
    String _siteName;
    String _ssid;
    const char* _fwVersion;
};

#endif
