#ifndef WIFICITIES_FILE_SERVER_H
#define WIFICITIES_FILE_SERVER_H

#include <ESPAsyncWebServer.h>
#include <LittleFS.h>

class FileServer {
public:
    FileServer();

    // Register the catch-all file serving handler (should be called LAST,
    // after all API/admin/plugin routes are registered)
    void registerRoutes(AsyncWebServer* server);

private:
    // Resolve a URL path to a filesystem path using folder-based routing
    // Returns empty string if no file found
    static String _resolvePath(const String& urlPath);

    // Get MIME type from file extension
    static const char* _getMimeType(const String& path);

    // Handle a file request
    static void _handleFileRequest(AsyncWebServerRequest* request);
};

#endif
