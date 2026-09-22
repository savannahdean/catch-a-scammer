#include "http.h"

#include <curl/curl.h>

#include <chrono>

namespace net {
namespace {

size_t WriteCb(char* ptr, size_t size, size_t nmemb, void* userdata) {
    auto* out = static_cast<std::string*>(userdata);
    out->append(ptr, size * nmemb);
    return size * nmemb;
}

Response Perform(const std::string& url, const char* method,
                 const std::string& body) {
    Response r;
    CURL* curl = curl_easy_init();
    if (!curl) {
        r.error = "could not initialise libcurl";
        return r;
    }
    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    headers = curl_slist_append(headers, "Accept: application/json");

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &r.body);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 25L);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 8L);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L);
    curl_easy_setopt(curl, CURLOPT_USERAGENT, "sleuthos-client/1.0");

    if (std::string(method) == "POST") {
        curl_easy_setopt(curl, CURLOPT_POST, 1L);
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, body.c_str());
        curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, (long)body.size());
    } else if (std::string(method) == "DELETE") {
        curl_easy_setopt(curl, CURLOPT_CUSTOMREQUEST, "DELETE");
    }

    CURLcode rc = curl_easy_perform(curl);
    if (rc != CURLE_OK) {
        r.error = curl_easy_strerror(rc);
    } else {
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &r.status);
    }
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    return r;
}

}  // namespace

void GlobalInit() { curl_global_init(CURL_GLOBAL_DEFAULT); }
void GlobalShutdown() { curl_global_cleanup(); }

std::string UrlEncode(const std::string& s) {
    CURL* curl = curl_easy_init();
    if (!curl) return s;
    char* esc = curl_easy_escape(curl, s.c_str(), (int)s.size());
    std::string out = esc ? esc : s;
    if (esc) curl_free(esc);
    curl_easy_cleanup(curl);
    return out;
}

std::string BuildUrl(const std::string& base, const std::string& path,
                     const Params& params) {
    std::string url = base;
    if (!url.empty() && url.back() == '/') url.pop_back();
    url += path;
    bool first = true;
    for (const auto& kv : params) {
        url += first ? "?" : "&";
        first = false;
        url += UrlEncode(kv.first) + "=" + UrlEncode(kv.second);
    }
    return url;
}

Response Get(const std::string& url) { return Perform(url, "GET", ""); }
Response Post(const std::string& url, const std::string& b) {
    return Perform(url, "POST", b);
}
Response Delete(const std::string& url) { return Perform(url, "DELETE", ""); }

void Async::start(std::function<Response()> fn) {
    fut_ = std::async(std::launch::async, std::move(fn));
    pending_ = true;
}

bool Async::ready() {
    if (!pending_ || !fut_.valid()) return false;
    return fut_.wait_for(std::chrono::seconds(0)) == std::future_status::ready;
}

Response Async::take() {
    pending_ = false;
    if (!fut_.valid()) {
        Response r;
        r.error = "no request in flight";
        return r;
    }
    return fut_.get();
}

}  // namespace net
