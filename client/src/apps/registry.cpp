#include "app.h"
#include "factories.h"

// Order here is the order of the desktop icons, the taskbar and the start
// menu. It follows the investigation itself: you read the case, resolve the
// indicators, read the reporting, look up the actor, then file the report.
std::vector<std::unique_ptr<App>> MakeApps() {
    std::vector<std::unique_ptr<App>> apps;
    apps.push_back(MakeCaseDesk());
    apps.push_back(MakeIntelSearch());
    apps.push_back(MakeMalwareDb());
    apps.push_back(MakeWebSearch());
    apps.push_back(MakeDirectory());
    apps.push_back(MakeEvidenceMap());
    apps.push_back(MakeCaseReport());
    return apps;
}
