#pragma once
#include <memory>

#include "app.h"

std::unique_ptr<App> MakeCaseDesk();
std::unique_ptr<App> MakeIntelSearch();
std::unique_ptr<App> MakeWebSearch();
std::unique_ptr<App> MakeDirectory();
std::unique_ptr<App> MakeMalwareDb();
std::unique_ptr<App> MakeEvidenceMap();
std::unique_ptr<App> MakeCaseReport();
