#pragma once
#include <future>
#include <string>
#include <utility>
#include <vector>

namespace net {

struct Response {
    long status = 0;
    std::string body;
    std::string error;  // transport-level failure, empty on success
    bool ok() const { return error.empty() && status >= 200 && status < 300; }
};

void GlobalInit();
void GlobalShutdown();

std::string UrlEncode(const std::string& s);

using Params = std::vector<std::pair<std::string, std::string>>;
std::string BuildUrl(const std::string& base, const std::string& path,
                     const Params& params);

Response Get(const std::string& url);
Response Post(const std::string& url, const std::string& jsonBody);
Response Delete(const std::string& url);

// One in-flight request. Poll ready() every frame; take() moves the result out.
class Async {
  public:
    void start(std::function<Response()> fn);
    bool pending() const { return pending_; }
    bool ready();
    Response take();
    void cancel() { pending_ = false; }

  private:
    std::future<Response> fut_;
    bool pending_ = false;
};

}  // namespace net
