// The query tools. They share one class because they differ only in which
// endpoint they hit and what they tell the player to type: the server
// describes every result, so a new tool is one Make*() function below.
#include <algorithm>
#include <vector>

#include "../core/theme.h"
#include "../ui/widgets.h"
#include "common.h"
#include "factories.h"

namespace {

class LookupApp : public App {
  public:
    LookupApp(std::string id, std::string title, std::string glyph, Color accent,
              std::string path, std::string placeholder, std::string blurb)
        : id_(std::move(id)),
          title_(std::move(title)),
          glyph_(std::move(glyph)),
          accent_(accent),
          path_(std::move(path)),
          placeholder_(std::move(placeholder)),
          blurb_(std::move(blurb)) {}

    std::string Id() const override { return id_; }
    std::string Title() const override { return title_; }
    std::string Glyph() const override { return glyph_; }
    Color Accent() const override { return accent_; }

    void OnOpen(Session& s, const std::string& query) override {
        if (query.empty()) return;
        // another window handed over one record to show ("@fetch:<url>")
        const std::string tag = "@fetch:";
        if (query.rfind(tag, 0) == 0) {
            if (finder_.result.is_object() && !finder_.result.empty())
                history_.push_back(finder_.result);
            finder_.Fetch(s, query.substr(tag.size()));
            return;
        }
        finder_.field.text = query;
        history_.clear();
        finder_.Search(s, path_, query);
    }

    void Draw(Session& s, Rectangle c, bool active) override {
        finder_.Poll(s);
        (void)active;

        // ---- query bar
        Rectangle bar{c.x, c.y, c.width, 54.0f};
        DrawRectangleRec(bar, Color{238, 241, 246, 255});
        DrawLineEx({bar.x, bar.y + bar.height}, {bar.x + bar.width, bar.y + bar.height},
                   1.0f, Color{210, 216, 224, 255});

        bool back = !history_.empty();
        float bx = bar.x + theme::PAD;
        if (back) {
            if (ui::Button({bx, bar.y + 13.0f, 70.0f, 28.0f}, "< BACK")) {
                finder_.result = history_.back();
                history_.pop_back();
                finder_.scroll.y = 0.0f;
            }
            bx += 78.0f;
        }
        Rectangle field{bx, bar.y + 13.0f, c.width - (bx - bar.x) - 200.0f, 28.0f};
        bool enter = ui::TextFieldW(finder_.field, field, placeholder_);
        Rectangle go{field.x + field.width + 8.0f, bar.y + 13.0f, 90.0f, 28.0f};
        bool clicked = ui::Button(go, "SEARCH", s.hasCase() && !finder_.busy());
        Rectangle clr{go.x + 98.0f, bar.y + 13.0f, 74.0f, 28.0f};
        if (ui::Button(clr, "CLEAR")) {
            finder_.field.text.clear();
            finder_.Reset();
            history_.clear();
        }

        if ((enter || clicked) && s.hasCase()) {
            history_.clear();
            finder_.Search(s, path_, finder_.field.text);
        }

        // ---- body
        Rectangle body{c.x, c.y + 54.0f, c.width, c.height - 54.0f};
        DrawRectangleRec(body, theme::WIN_BODY);
        Rectangle inner{body.x + theme::PAD, body.y + theme::PAD,
                        body.width - theme::PAD * 2.0f,
                        body.height - theme::PAD * 2.0f};

        if (!s.hasCase()) {
            theme::TextWrapped(theme::UI(),
                               "No case is open. Open CaseDesk and request a "
                               "case file before querying the indexes.",
                               inner, 14.0f, theme::TEXT_DIM);
            return;
        }

        if (finder_.busy()) {
            ui::Spinner({inner.x + inner.width * 0.5f, inner.y + 80.0f}, 16.0f,
                        theme::ACCENT);
            std::string msg = "Querying index for \"" + finder_.pendingQuery + "\"";
            float w = theme::TextW(theme::UI(), msg, 13.0f);
            theme::Text(theme::UI(), msg, inner.x + (inner.width - w) * 0.5f,
                        inner.y + 112.0f, 13.0f, theme::TEXT_DIM);
            return;
        }

        rec::Action action;
        ui::BeginScroll(finder_.scroll, inner);
        float y = inner.y - finder_.scroll.y;

        if (!finder_.error.empty()) {
            y = rec::Empty(finder_.error, inner, y);
        } else if (finder_.result.is_object() &&
                   (finder_.result.contains("kind") || finder_.result.contains("card"))) {
            y = rec::Single(s, finder_.result, inner, y, action);
        } else if (finder_.result.is_object() && finder_.result.contains("query")) {
            if (!jbool(finder_.result, "found")) {
                y = rec::Empty(jstr(finder_.result, "message", "No results."),
                               inner, y);
            } else {
                y = rec::Envelope(s, finder_.result, inner, y, action);
            }
        } else {
            y += theme::TextWrapped(theme::UI(), blurb_,
                                    {inner.x, y, inner.width - 20.0f, 400.0f},
                                    14.0f, theme::TEXT_DIM);
        }
        ui::EndScroll(finder_.scroll, inner, y - (inner.y - finder_.scroll.y));

        if (action.kind == rec::Action::FetchUrl &&
            (action.app.empty() || action.app == id_)) {
            history_.push_back(finder_.result);
            finder_.Fetch(s, action.url);
        } else {
            rec::Apply(s, action);
        }
    }

  private:
    std::string id_, title_, glyph_;
    Color accent_;
    std::string path_, placeholder_, blurb_;
    rec::Finder finder_;
    std::vector<json> history_;
};

}  // namespace

std::unique_ptr<App> MakeIntelSearch() {
    return std::make_unique<LookupApp>(
        "intelsearch", "IntelSearch - Threat Intelligence", "IS",
        theme::ACCENT, "/api/intel", "domain, URL or IP address",
        "IntelSearch queries the threat-intelligence index.\n\n"
        "Paste the link from the victim's statement. A malicious domain will "
        "usually resolve to an address, and that address will usually be "
        "hosting more than one thing.\n\n"
        "Accepted input:\n"
        "    secure-account-check.example\n"
        "    https://secure-account-check.example/login\n"
        "    203.0.113.42\n\n"
        "Remember that co-hosting is not attribution. Other domains on the "
        "same address may have nothing to do with this incident.");
}

std::unique_ptr<App> MakeMalwareDb() {
    return std::make_unique<LookupApp>(
        "malwaredb", "MalwareDB - Family Index", "MW", theme::DANGER,
        "/api/malware", "malware family, SHA-256, MD5 or file name",
        "MalwareDB indexes malware families, the campaigns they have been "
        "seen in, and the infrastructure they beacon to. It also holds file "
        "analyses: search a SHA-256, MD5 or file name to see antivirus "
        "detections, YARA matches, strings and the extracted configuration.\n\n"
        "Families are shared between unrelated crews, so prefer the one that "
        "was actually staged on the domain your victim visited. Strings that "
        "name a famous group are trivial to plant.");
}

std::unique_ptr<App> MakeDirectory() {
    return std::make_unique<LookupApp>(
        "directory", "Directory - People and Aliases", "DIR", theme::NOISE,
        "/api/directory", "alias, name, email or username",
        "Directory is a people-search index. It holds two very different kinds "
        "of record in one place:\n\n"
        "    - threat actor aliases, with their tracked campaigns and "
        "infrastructure\n"
        "    - civilian records, including breach exposure\n\n"
        "Search an alias you picked up from published reporting, or look up "
        "the reporting party from your case file.");
}

std::unique_ptr<App> MakeWebSearch() {
    return std::make_unique<LookupApp>(
        "websearch", "Web Search", "WS", theme::OK, "/api/websearch",
        "campaign name, malware family or alias",
        "A search over public security writing: blogs, community reports, "
        "and researcher notes.\n\n"
        "This is where attribution comes from. Infrastructure tells you what "
        "happened; published reporting tells you who somebody thinks did it.\n\n"
        "Try a campaign name. Read carefully -- not every article names an "
        "actor, and some of them are about entirely different activity.\n\n"
        "Searching an indicator (a handle, a phone number, an account, a "
        "wallet) finds any reporting that lists it.");
}

// ------------------------------------------------------------------------
// People, messages and money: the tools the non-phishing scams need.

std::unique_ptr<App> MakeSocial() {
    return std::make_unique<LookupApp>(
        "social", "Social Search - Profiles and Posts", "SOC", Color{196, 72, 120, 255},
        "/api/social", "@handle, name, or a phrase from a message",
        "Searches public profiles, posts and the direct messages in this case "
        "across every platform, including criminal forums.\n\n"
        "Paste a phrase from a message the victim received and you get the "
        "message and the profile that sent it. Search a username and you get "
        "every account using it, on any platform.\n\n"
        "What to check on a profile:\n"
        "    - how old the account is compared to when contact started\n"
        "    - whether the photos belong to someone else (Reverse Image)\n"
        "    - whether the same handle exists elsewhere, and who that is\n\n"
        "A similar handle is not the same person. Look for something that "
        "actually links two accounts.");
}

std::unique_ptr<App> MakeReverseImage() {
    return std::make_unique<LookupApp>(
        "reverseimage", "Reverse Image Search", "IMG", Color{150, 96, 196, 255},
        "/api/reverseimage", "image ID (img:...) or perceptual hash",
        "Finds every place a picture, or a resized or recompressed copy of "
        "it, has appeared, oldest first.\n\n"
        "Catfish and investment scammers rarely use their own face. If a "
        "profile created last month uses a photo first posted years ago by "
        "someone else, you have found a stolen identity.\n\n"
        "If there is no earlier copy, check the AI-face detector score. A "
        "generated face has no real owner to find.\n\n"
        "Click REVERSE IMAGE SEARCH on any profile photo, or paste its Image ID.");
}

std::unique_ptr<App> MakePhone() {
    return std::make_unique<LookupApp>(
        "phone", "Phone Lookup - Carrier and Reputation", "TEL", Color{40, 150, 140, 255},
        "/api/phone", "phone number in any format",
        "Carrier lookup: who issued the number, what kind of line it is, the "
        "caller-ID name on file, and how many people have reported it.\n\n"
        "VoIP and toll-free numbers can be rented in minutes and dropped just "
        "as fast. A bank or support desk calling from one is a red flag.\n\n"
        "Caller ID is easy to fake. The number that showed up on the victim's "
        "phone tells you little. A number the scammer told them to call back "
        "is a real lead.");
}

std::unique_ptr<App> MakeSms() {
    return std::make_unique<LookupApp>(
        "sms", "Spam Text Reports", "SMS", Color{46, 132, 196, 255},
        "/api/sms", "sending number or text from the message",
        "Carrier database of text messages people reported as spam (the "
        "messages forwarded to 7726).\n\n"
        "Search the sender's number to see everything else it sent, or a "
        "phrase to find the same lure sent from other numbers. Smishing crews "
        "rotate numbers but reuse wording.");
}

std::unique_ptr<App> MakeDocLab() {
    return std::make_unique<LookupApp>(
        "doclab", "Document Lab - Metadata", "DOC", Color{120, 110, 60, 255},
        "/api/documents", "file name, author, text or SHA-256",
        "Reads the metadata hidden inside documents: author, last editor, "
        "organization, the program that made it, and when.\n\n"
        "Forgers polish what the page says and forget what the file says. An "
        "official certificate written last week by a private individual in a "
        "free editor did not come from an official.\n\n"
        "Search an author's name to find their other documents.");
}

std::unique_ptr<App> MakeAudioLab() {
    return std::make_unique<LookupApp>(
        "audiolab", "Audio Lab - Voice Analysis", "AUD", Color{200, 110, 40, 255},
        "/api/audio", "transcript text, speaker, caller ID or voiceprint",
        "Analyzes recordings: transcript, the caller ID that was displayed, "
        "STIR/SHAKEN attestation, a voiceprint (speaker fingerprint) and a "
        "synthetic-voice detector score.\n\n"
        "Voice cloning needs a sample of the real person, usually a public "
        "talk or video. Search for public recordings of the person the caller "
        "claimed to be and compare voiceprints.\n\n"
        "Attestation C means the call came in through a gateway and the "
        "caller ID was never verified.");
}

std::unique_ptr<App> MakePayments() {
    return std::make_unique<LookupApp>(
        "payments", "Payment Account Lookup", "PAY", Color{36, 120, 70, 255},
        "/api/payments", "account number, payment handle, provider or wallet",
        "Looks up bank accounts, payment-app handles, gift-card purchases and "
        "crypto wallets.\n\n"
        "Gift cards and crypto are what scammers ask for because the payments "
        "are hard to reverse. No real bank, government office or support desk "
        "asks to be paid in them.\n\n"
        "Accounts receiving fraud are often money mules: real people recruited "
        "to pass the money along. Follow the money past them.");
}

std::unique_ptr<App> MakeMoneyTrail() {
    return std::make_unique<LookupApp>(
        "moneytrail", "Money Trail - Follow the Funds", "$", Color{20, 110, 60, 255},
        "/api/moneytrail", "account identifier or wallet address (or its start)",
        "Follows money forward from an account or wallet, one transfer at a "
        "time, to where it stopped.\n\n"
        "Criminals move stolen funds through several wallets (layering) so the "
        "trail looks cold. It usually ends at an exchange deposit address, the "
        "point where crypto becomes cash and an identity is on file.\n\n"
        "You can type just the first characters of an address; the tool lists "
        "the matches.");
}

std::unique_ptr<App> MakeComplaints() {
    return std::make_unique<LookupApp>(
        "complaints", "ScamWatch - Fraud Reports", "SW", Color{170, 60, 60, 255},
        "/api/complaints", "phone, handle, domain, wallet or keyword",
        "Reports other victims filed with the ScamWatch fraud portal.\n\n"
        "Several reports naming the same number, account or handle show you "
        "are looking at an operation, not a one-off. Reports are unverified, "
        "and similar stories often come from different crews, so match on "
        "indicators, not on the story.");
}

// ------------------------------------------------------------------------
// Infrastructure: the tools that turn a link into an operator.

std::unique_ptr<App> MakeDns() {
    return std::make_unique<LookupApp>(
        "dns", "DNS History - Passive DNS", "DNS", Color{30, 100, 150, 255},
        "/api/dns", "domain or IP address",
        "Every resolution of a domain to an address that sensors have "
        "observed, with first-seen and last-seen dates. Works both ways: "
        "search an address to see every domain that pointed at it.\n\n"
        "Compare the dates with the incident. After a takedown, domains often "
        "point at a sinkhole; behind a CDN they point at a shared edge server. "
        "Neither is the attacker. The origin is usually in the older history.");
}

std::unique_ptr<App> MakeWhois() {
    return std::make_unique<LookupApp>(
        "whois", "WHOIS History", "WHO", Color{90, 90, 150, 255},
        "/api/whois", "domain, or a registrant email",
        "Every captured snapshot of a domain's registration record.\n\n"
        "Today most records say REDACTED FOR PRIVACY. Snapshots taken in the "
        "first hours after registration sometimes caught the real registrant "
        "before privacy was switched on. An email found there can be searched "
        "in breach data.\n\n"
        "Search a registrant email to find every domain it registered.");
}

std::unique_ptr<App> MakeCerts() {
    return std::make_unique<LookupApp>(
        "certs", "CertSearch - Certificate Transparency", "CT", Color{60, 130, 110, 255},
        "/api/certs", "domain or part of one",
        "Searches the public certificate-transparency logs. Every TLS "
        "certificate is logged, with every name it covers.\n\n"
        "Attackers often request one certificate for several of their domains "
        "at once, which links them. A CDN's shared certificate covers "
        "thousands of unrelated customers and links nothing.");
}

std::unique_ptr<App> MakeUrlScan() {
    return std::make_unique<LookupApp>(
        "urlscan", "URL Scanner", "URL", Color{180, 90, 40, 255},
        "/api/urlscan", "URL, domain or IP address",
        "Sandboxed scans of web pages: final URL after redirects, page title, "
        "server, the IP it was served from, and fingerprints you can pivot on: "
        "analytics tracking IDs, favicon hash, JARM TLS fingerprint, and "
        "phishing-kit leftovers.\n\n"
        "A tracking ID or JARM fingerprint shared with other pages usually "
        "means the same operator. A favicon only means the same brand was "
        "copied.");
}

std::unique_ptr<App> MakeBreach() {
    return std::make_unique<LookupApp>(
        "breach", "Breach Lookup", "BR", Color{110, 70, 50, 255},
        "/api/breach", "exact email address or username",
        "Searches leaked user tables from breached websites for an exact "
        "email address or username.\n\n"
        "People reuse emails and usernames for years. An address found in a "
        "WHOIS record or a forum's leaked user list can lead to an old gaming "
        "or social account, and from there to a real name.\n\n"
        "Passwords are never shown, only that a record exists and what it "
        "contained.");
}
