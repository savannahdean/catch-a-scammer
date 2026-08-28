# catch-a-scammer
MySQL implementation and testing enviornment for our Database Management Systems group project

# Project Overview: 
catch-a-scammer is a game designed as an Open Source Intelligence (OSINT) investigation platform in which the player takes the role of a digital investigator.

The player recieves a simulated cybersecurity case involving a victim, suspicious communication, malicious infrastructure, or another digital clue.

The player must investigate the availble evidence, search through databases, identify relationships between entities, and ultimately determine who or what is responsible for the incident.

# Central Concept
start with one clue --> investigate it --> discover related entities --> follow the relationships
--> build enough evidence to solve the case.

# This project includes:
- TBD

# The Core Gameplay Loop:

Step 1 - Recieve a Case
The player logs into the investigator interface and recieve something like:

CASE #102321

A University employee reports that their banking credentials may have been stolen.

The victim received and email containing:
https://secure-account-example.com/login

The email was recieved on:
March 14th, 2026 - 9:42 PM

The victim rememvers clicking the link.

Objective: Identify the malicious infrastructure and determine the actor responsible.

Creation of a fictional operating system.

# CaseDesk
Where the player reads the case.
- A ticketing system of sorts where the player gets their initial clue.
- eg: suspicious-account-check.example

# IntelSearch
The applications threat-intelligence database.

- here you can search for "suspicious-account-check.example"
- RESULTS:
- First Seen:       2026-02-17
- Last Seen:        2026-03-15
- Status:           MALICIOUS
- Associated IPs:   203.0.113.42
                      [VIEW IP]

[ADD TO EVIDENCE]        [OPEN GRAPH]

NEW CLUE: 203.0.113.42
- player SHOULD View IP
- This will show
APPROX. LOCATION
United States
Tennessee

NETWORK INFORMATION:

ASN: AS12345
Organization: Example Hosting LLC

RELATED DOMAINS:

suspicious-account-check.example
account-verification.example
secure-billing.example

RELATED MALWARE

ExampleStealer

[VIEW MALWARE]

- Now the player can investigate the other domains.
- Say they click:
account.verification.example

STATUS: MALICIOUS
FIRST SEEN: 2026-02-20
Associated Malware: ExampleStealer
Associated Campaign: Operation Example

Now they have: Domain A --> IP --> Domain B --> Malware --> Campaign
At any point the player can open The Evidence Map

# Evidence Map:
**EVIDENCE DOESNT MEAN CORRECT!!!!!
The relationship / graph visualization.

                                                        _________________________________
                                                        |                               |
                                                        |             DOMAIN            |
                                                        |  suspicious-account.example   |
                                                        |_______________________________|
                                                                        |
                                                                        |
                                                                        V
                                                        _________________________________
                                                        |                               |
                                                        |               IP              |
                                                        |          203.0.113.42         |
                                                        |_______________________________|
                                                                        |
                                        _______________________________ | _______________________________
                                        |                                                               |
                                        |                                                               |
                                        V                                                               V

[INVESTIGATE NODE] [EVIDENCE] [CASE FILE]

**THINGS TO NOTE**
Some of these domains and IPs may be noise, they may not be related to the case at all! the more information thrown at the user the better. For replayability and 
making the game more of an investigation like real life.
                                      
# Web Search
A fictional Search Engine

Search a URL, maybe it comes up with a threatwatch blog, or a security form. The results will be FICTIONAL

"Researchers have linked this campaign to the alias NIGHTFALL"
Which could lead them to the Threat Actor Database.

# Directory:
Your fictional people/company database.

Search: NIGHTFALL
RESULTS:
Threat ACtor Alias
Known Campiagns: 3
Known Malware: 2
Known Infrastructure: 17

[VIEW PROFILE]
- shows specifics

# Malware DB:
Malware Information.

Search: ExampleStealer

FAMILY: ExampleStealer
TYPE:Information Stealer
FIRST OBSERVED: 2026-01-08
ASSOCIATED CAMPAIGNS:
--> Operation X
--> Campaign Y

ASSOCIATED INFRASTRUCTURE:
--> 203.0.113.42
-->198.51.100.12

HASHES
SHA256: abc123...

SOURCES:
MalwareBazaar

# Case Report:
Where the playere ultimately submits their conclusion.

WHO IS RESPONSIBLE?
ASSOCIATED CAMPAIGN:
PRIMARY MALICIOUS DOMAIN:

select supporting evidence:

* domain
* IP
* Malware
* Campaign
* Secondary Domain

--------------------------------------------------------------------------------------------------------------------------------------
# ROADMAP:

Step 1: Tables

------------------

cases — the case file: case code, victim summary, briefing text, whether it's solved, and which entity/campaign is the correct answer.
domains — domain names, whether each is malicious/benign/unknown, and first/last seen dates.
ip_addresses — IP addresses, which hosting provider they belong to, and their ASN/country/region.
hosting_providers — just an id and a company name (e.g. "Example Hosting LLC").
malware — malware family name, type, first observed date, optional hash, and source.
campaigns — named campaigns (e.g. "Operation Example") that group malware and threat actors.
threat_actors — the person/group behind it all, identified by an alias, with notes.
web_articles — fake blog/news snippets, each pointing at a domain or threat actor.
evidence — items the player collects during a case.
entity_relationships — the glue table that says "this thing connects to that thing" for every pair above, so you don't need a separate table for every possible relationship.