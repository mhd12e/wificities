#include "file_server.h"

FileServer::FileServer() {}

String FileServer::_resolvePath(const String& urlPath) {
    String path = urlPath;

    // Normalize: remove trailing slash (except root)
    if (path.length() > 1 && path.endsWith("/")) {
        path = path.substring(0, path.length() - 1);
    }

    // Security: reject path traversal
    if (path.indexOf("..") >= 0) {
        return "";
    }

    String fullPath = "/public" + path;

    // Rule 1: Exact file match
    if (LittleFS.exists(fullPath)) {
        File f = LittleFS.open(fullPath, "r");
        if (f && !f.isDirectory()) {
            f.close();
            return fullPath;
        }
        if (f) f.close();
    }

    // Rule 2: Directory index (path/index.html)
    String indexPath = fullPath + "/index.html";
    if (LittleFS.exists(indexPath)) {
        return indexPath;
    }

    // Rule 3: HTML fallback (path.html)
    String htmlPath = fullPath + ".html";
    if (LittleFS.exists(htmlPath)) {
        return htmlPath;
    }

    return "";
}

const char* FileServer::_getMimeType(const String& path) {
    if (path.endsWith(".html") || path.endsWith(".htm")) return "text/html";
    if (path.endsWith(".css"))  return "text/css";
    if (path.endsWith(".js"))   return "application/javascript";
    if (path.endsWith(".json")) return "application/json";
    if (path.endsWith(".png"))  return "image/png";
    if (path.endsWith(".jpg") || path.endsWith(".jpeg")) return "image/jpeg";
    if (path.endsWith(".gif"))  return "image/gif";
    if (path.endsWith(".ico"))  return "image/x-icon";
    if (path.endsWith(".svg"))  return "image/svg+xml";
    if (path.endsWith(".woff")) return "font/woff";
    if (path.endsWith(".woff2")) return "font/woff2";
    if (path.endsWith(".ttf"))  return "font/ttf";
    if (path.endsWith(".mp3"))  return "audio/mpeg";
    if (path.endsWith(".wav"))  return "audio/wav";
    if (path.endsWith(".mid") || path.endsWith(".midi")) return "audio/midi";
    if (path.endsWith(".txt"))  return "text/plain";
    if (path.endsWith(".xml"))  return "application/xml";
    return "application/octet-stream";
}

void FileServer::_handleFileRequest(AsyncWebServerRequest* request) {
    String urlPath = request->url();

    String filePath = _resolvePath(urlPath);

    if (filePath.length() == 0) {
        // Try custom 404 page
        if (LittleFS.exists("/public/404.html")) {
            request->send(LittleFS, "/public/404.html", "text/html");
        } else {
            request->send(404, "text/html",
                "<!DOCTYPE html><html><body style=\"font-family:monospace;text-align:center;padding:50px;\">"
                "<h1>404</h1><p>Page not found.</p>"
                "<p><a href=\"/\">Go home</a></p></body></html>");
        }
        return;
    }

    const char* mime = _getMimeType(filePath);

    AsyncWebServerResponse* response = request->beginResponse(LittleFS, filePath, mime);

    // Cache headers: cache assets, not HTML
    if (String(mime).startsWith("text/html")) {
        response->addHeader("Cache-Control", "no-cache");
    } else {
        response->addHeader("Cache-Control", "max-age=86400");
    }

    request->send(response);
}

void FileServer::registerRoutes(AsyncWebServer* server) {
    // Catch-all handler — lowest priority, registered last
    server->onNotFound(_handleFileRequest);
}
