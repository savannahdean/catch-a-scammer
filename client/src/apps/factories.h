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

// people, messages and money
std::unique_ptr<App> MakeSocial();
std::unique_ptr<App> MakeReverseImage();
std::unique_ptr<App> MakePhone();
std::unique_ptr<App> MakeSms();
std::unique_ptr<App> MakeDocLab();
std::unique_ptr<App> MakeAudioLab();
std::unique_ptr<App> MakePayments();
std::unique_ptr<App> MakeMoneyTrail();
std::unique_ptr<App> MakeComplaints();

// infrastructure
std::unique_ptr<App> MakeDns();
std::unique_ptr<App> MakeWhois();
std::unique_ptr<App> MakeCerts();
std::unique_ptr<App> MakeUrlScan();
std::unique_ptr<App> MakeBreach();
