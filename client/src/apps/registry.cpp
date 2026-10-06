#include "app.h"
#include "factories.h"

// Order here is the order of the desktop icons, the taskbar and the start
// menu. It follows the investigation itself: read the case, run down the
// infrastructure, work the people, messages and money, read the reporting,
// then file the report.
std::vector<std::unique_ptr<App>> MakeApps() {
    std::vector<std::unique_ptr<App>> apps;
    apps.push_back(MakeCaseDesk());
    // infrastructure
    apps.push_back(MakeIntelSearch());
    apps.push_back(MakeDns());
    apps.push_back(MakeWhois());
    apps.push_back(MakeCerts());
    apps.push_back(MakeUrlScan());
    apps.push_back(MakeMalwareDb());
    // people, messages and money
    apps.push_back(MakeSocial());
    apps.push_back(MakeReverseImage());
    apps.push_back(MakePhone());
    apps.push_back(MakeSms());
    apps.push_back(MakeAudioLab());
    apps.push_back(MakeDocLab());
    apps.push_back(MakePayments());
    apps.push_back(MakeMoneyTrail());
    apps.push_back(MakeComplaints());
    apps.push_back(MakeBreach());
    // reporting and attribution
    apps.push_back(MakeWebSearch());
    apps.push_back(MakeDirectory());
    apps.push_back(MakeEvidenceMap());
    apps.push_back(MakeCaseReport());
    return apps;
}
