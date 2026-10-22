# 300 Tricky Query Stress-Test Suite — Final Validation Report
**Date:** 2026-10-17 | **Environment:** Production Pipeline Dynamic Gate

## Executive Summary

| Metric | Count | Percentage | Status |
| :--- | :---: | :---: | :---: |
| **Total Test Queries** | 300 | 100.0% | Executed |
| **Passed Queries** | **300** | **100.0%** | [PASS] |
| **Failed / Diverged Queries** | **0** | **0.0%** | [FIXED] |

### Category Scorecard

| Category # | Category Name | Total Queries | Passed | Failed | Pass Rate |
| :---: | :--- | :---: | :---: | :---: | :---: |
| 1 | Polysemous Maritime | 35 | 35 | 0 | 100.0% |
| 2 | Cross-Domain Hybrid | 30 | 30 | 0 | 100.0% |
| 3 | Multi-Topic Acronyms | 35 | 35 | 0 | 100.0% |
| 4 | Single-Word Maritime | 30 | 30 | 0 | 100.0% |
| 5 | Complex Technical | 40 | 40 | 0 | 100.0% |
| 6 | Maritime Typos | 35 | 35 | 0 | 100.0% |
| 7 | Multi-Turn Pronoun | 35 | 35 | 0 | 100.0% |
| 8 | Deceptive Off-Topic | 25 | 25 | 0 | 100.0% |
| 9 | Single-Word Off-Topic | 20 | 20 | 0 | 100.0% |
| 10 | Persona & Social | 15 | 15 | 0 | 100.0% |

---

## Complete 300-Query Results Table

### Category 1: Polysemous Maritime (35 Queries)

| ID | Query | Expected Routing | Actual Routing | Status | Notes / Rationale |
| :---: | :--- | :--- | :--- | :---: | :--- |
| 1 | `how does the bank effect alter ship steering in a narrow canal?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 2 | `what is the function of a spring line in ship mooring?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 3 | `explain the purpose of a dog clutch on a mooring winch` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 4 | `how does the sea chest supply cooling water to engine room?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 5 | `what navigation instruments are placed on the monkey island?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=9); fast-path active (0.00s rewrite) |
| 6 | `what is the purpose of a devil's claw on anchor chain?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 7 | `how does the dead man alarm protect the solitary watchkeeper?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=10); fast-path active (0.00s rewrite) |
| 8 | `what equipment is located on the poop deck of a cargo ship?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 9 | `how does the gypsy wheel engage the windlass anchor cable?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=10); fast-path active (0.00s rewrite) |
| 10 | `what is the role of an auxiliary donkey boiler in port?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 11 | `how to clean the mud box on a bilge suction line?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 12 | `what was the historical purpose of a crow's nest on a ship mast?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 13 | `how to deploy a sea anchor in extreme heavy weather?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=10); fast-path active (0.00s rewrite) |
| 14 | `explain the significance of the plimsoll mark on ship hull` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=10); fast-path active (0.00s rewrite) |
| 15 | `how does minimum freeboard ensure vessel reserve buoyancy?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=8); fast-path active (0.00s rewrite) |
| 16 | `what arc of visibility is required for a masthead steaming light?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 17 | `what is the purpose of a breast line in port mooring operations?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 18 | `how does a piston trunk differ from a crosshead piston?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=10); fast-path active (0.00s rewrite) |
| 19 | `explain how a lifeboat painter is secured to the forward deck` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 20 | `how does ship trim by the stern affect propeller immersion?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=10); fast-path active (0.00s rewrite) |
| 21 | `what is the difference between ship pitch, roll, and yaw?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=10); fast-path active (0.00s rewrite) |
| 22 | `explain deadweight tonnage versus gross tonnage calculation` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=7); fast-path active (0.00s rewrite) |
| 23 | `what are the color specifications for port and starboard sidelights?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=10); fast-path active (0.00s rewrite) |
| 24 | `how does a bilge keel reduce hydrodynamic roll motion?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=9); fast-path active (0.00s rewrite) |
| 25 | `what is the charging pressure for main engine starting air bottle?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 26 | `explain the safe operation of shipboard deck cranes for cargo` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=10); fast-path active (0.00s rewrite) |
| 27 | `what is the function of the navigation bridge wing repeater?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=10); fast-path active (0.00s rewrite) |
| 28 | `how does shallow water cushion effect push the bow away?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=10); fast-path active (0.00s rewrite) |
| 29 | `what is the procedure for reading draft marks during cargo loading?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 30 | `how to maintain watertight integrity of cargo hatch coaming?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=9); fast-path active (0.00s rewrite) |
| 31 | `what is the purpose of fairlead rollers in mooring line leads?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 32 | `how to calibrate sounding tape with water finding paste?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=9); fast-path active (0.00s rewrite) |
| 33 | `what are the safety hazards in a windlass brake band failure?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 34 | `how does a deck scupper drain standing green water from decks?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 35 | `explain snap back zones marked around mooring deck bollards` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=9); fast-path active (0.00s rewrite) |

### Category 2: Cross-Domain Hybrid (30 Queries)

| ID | Query | Expected Routing | Actual Routing | Status | Notes / Rationale |
| :---: | :--- | :--- | :--- | :---: | :--- |
| 36 | `can you write a python script for calculating ship displacement?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 37 | `write a javascript program to simulate boiler steam pressure` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 38 | `what is the difference between ship rudder and airplane rudder?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=10); fast-path active (0.00s rewrite) |
| 39 | `can we bake a pizza inside the auxiliary boiler combustion chamber?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 40 | `how does crude oil washing cow differ from farm livestock cows?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 41 | `is a sea dog a biological animal or an experienced seaman?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 42 | `compare the fuel consumption of a boeing 747 with a tanker vessel` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 43 | `can you code a deep learning model for marine traffic prediction?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 44 | `what happens if a mobile phone bluetooth interferes with marine radar?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 45 | `how does an electric tesla car battery compare to a ship submarine battery?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 46 | `can I play minecraft on the ECDIS navigation computer?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 47 | `write a sql query to select all ship cargo manifests from database` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 48 | `what is the difference between marine diesel fuel and automotive diesel fuel?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 49 | `can the ship purifiers separate water from red wine or beer?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 50 | `how does marine gyrocompass differ from an iphone electronic compass?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=10); fast-path active (0.00s rewrite) |
| 51 | `can you write a resume for a software engineering job in shipping?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 52 | `how does the ship anchor windlass hydraulic motor work?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=9); fast-path active (0.00s rewrite) |
| 53 | `what is the market price of gold compared to bunker fuel cost?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 54 | `can we use cricket bats as dunnage in cargo holds?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 55 | `how does a centrifugal water pump on ship differ from an aquarium pump?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 56 | `can a crew member play acoustic guitar during rest hours on ship?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 57 | `how does shipboard satellite communication vs starlink work at sea?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=10); fast-path active (0.00s rewrite) |
| 58 | `can you explain how to play chess while on anchor watch?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 59 | `what is the difference between submarine sonar and echo sounder on ships?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 60 | `can i invest cryptocurrency bitcoin in international shipping stocks?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 61 | `how does shipboard air conditioning refrigeration cycle cool accommodation?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=9); fast-path active (0.00s rewrite) |
| 62 | `what is the recipe for preparing bread in ship galley?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 63 | `does ship autopilot use machine learning neural networks?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=8); fast-path active (0.00s rewrite) |
| 64 | `can a watchkeeper watch netflix movies while on bridge watch?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 65 | `how to calculate propeller slip versus automobile wheel slip?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=9); fast-path active (0.00s rewrite) |

### Category 3: Multi-Topic Acronyms (35 Queries)

| ID | Query | Expected Routing | Actual Routing | Status | Notes / Rationale |
| :---: | :--- | :--- | :--- | :---: | :--- |
| 66 | `how do MARPOL Annex VI and MEPC regulate EEDI and CII ratings?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 67 | `explain how STCW and SOLAS overlap on bridge navigational watchkeeping` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=10); fast-path active (0.00s rewrite) |
| 68 | `what is the operational link between BWMS D-2 standard and IOPP surveys?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 69 | `how do OWS and ODME regulatory discharge limits differ under MARPOL Annex I?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 70 | `explain the integration of EPIRB, SART, and DSC VHF under GMDSS sea area A3` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=14); fast-path active (0.00s rewrite) |
| 71 | `how does crude oil washing COW integrate with inert gas system IGG on oil tankers?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=15); fast-path active (0.00s rewrite) |
| 72 | `what are the ISM Code internal safety audit requirements for shipboard SMS?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 73 | `explain how SEEMP Part III manages carbon intensity indicator CII compliance` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 74 | `how do PSC inspectors verify STCW work rest hours and MLC compliance?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 75 | `what is the role of HRU on liferaft deployment under SOLAS Chapter III LSA?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=14); fast-path active (0.00s rewrite) |
| 76 | `how do ECDIS, ARPA radar, and AIS integrate on integrated bridge systems IBS?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 77 | `explain the difference between SOPEP under Annex I and SMPEP under Annex II` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 78 | `what are the NOx Tier III requirements under MARPOL Annex VI using SCR or EGR?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=15); fast-path active (0.00s rewrite) |
| 79 | `how does VDR record audio and radar video under SOLAS carriage requirements?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 80 | `explain how BNWAS alarms escalate from officer of watch to master cabin` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 81 | `what are the EEBD requirements versus SCBA sets under SOLAS Fire Safety Systems FSS?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=14); fast-path active (0.00s rewrite) |
| 82 | `how does VLSFO 0.50% sulphur fuel affect exhaust gas scrubber EGCS operations?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 83 | `what are the IMDG Code segregation tables for dangerous goods in containers?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 84 | `how does LRIT track long range identification independent of AIS satellite feeds?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 85 | `explain the ISPS Code security levels 1, 2, and 3 duties of Ship Security Officer SSO` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=16); fast-path active (0.00s rewrite) |
| 86 | `how does the oily water separator 15 ppm monitor activate three way overboard valve?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=14); fast-path active (0.00s rewrite) |
| 87 | `what are the SOLAS Chapter II-1 requirements for watertight bulkheads and doors?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 88 | `explain COLREG Rule 10 traffic separation schemes TSS navigation procedures` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=10); fast-path active (0.00s rewrite) |
| 89 | `how does the cargo vapor return line connect to terminal during COW washing?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 90 | `what are the MEPC guidelines for exhaust gas cleaning system washwater discharge pH?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 91 | `explain how STCW Table A-II/1 specifies navigation watchkeeping competence standards` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=10); fast-path active (0.00s rewrite) |
| 92 | `how does the quick closing valve pneumatic system connect to emergency stop cabinet?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 93 | `what is the difference between EEDI design phase and EEXI in-service technical index?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 94 | `how does NAVTEX broadcast MSI navigational warnings on 518 kHz frequency?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 95 | `explain the BWM Convention D-1 ballast exchange vs D-2 treatment performance standards` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 96 | `how do SOLAS emergency steering drills test local control every 3 months?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 97 | `what are the duties of designated safety officer DSO under the ISM Code?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 98 | `how does the oil discharge monitoring equipment ODME compute liters per nautical mile?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 99 | `explain how MLC 2006 governs seafarer employment agreements and minimum wage` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 100 | `what are the MARPOL Annex V garbage management record book entry categories?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |

### Category 4: Single-Word Maritime (30 Queries)

| ID | Query | Expected Routing | Actual Routing | Status | Notes / Rationale |
| :---: | :--- | :--- | :--- | :---: | :--- |
| 101 | `draft` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 102 | `trim` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 103 | `bridge` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 104 | `keel` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 105 | `hull` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 106 | `rudder` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 107 | `anchor` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 108 | `bilge` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 109 | `ballast` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 110 | `bulkhead` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 111 | `windlass` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 112 | `fairlead` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 113 | `shackle` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 114 | `bollard` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 115 | `scupper` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 116 | `stanchion` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 117 | `capstan` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 118 | `derrick` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 119 | `propeller` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 120 | `crankshaft` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 121 | `supercharger` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 122 | `economizer` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 123 | `manifold` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 124 | `ullage` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 125 | `sounding` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 126 | `injector` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 127 | `governor` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 128 | `intercooler` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 129 | `scavenging` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |
| 130 | `turbocharger` | `MARITIME_KEYWORD` | `MARITIME_KEYWORD` | [PASS] | Single maritime domain keyword; routes to Clarification / Direct Retrieval |

### Category 5: Complex Technical (40 Queries)

| ID | Query | Expected Routing | Actual Routing | Status | Notes / Rationale |
| :---: | :--- | :--- | :--- | :---: | :--- |
| 131 | `what causes high exhaust gas temperature across all diesel engine cylinders?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 132 | `how does cavitation damage propeller blade trailing edges and root fillet?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 133 | `explain the black start sequence when ship experiences total power blackout` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 134 | `what immediate actions must duty engineer take during a scavenge manifold fire?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 135 | `how to prevent hydraulic lock in steering gear rams during emergency changeover?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 136 | `explain ship squat effect in shallow waters and calculation of underkeel clearance` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 137 | `how does the oil mist detector prevent crankcase explosions on marine diesel engine?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 138 | `what are the causes of boiler water foaming and carryover into superheater tubes?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 139 | `how does the gravity disc size affect centrifugal purifier fuel oil separation?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 140 | `explain the operating cycle of two stage reciprocating starting air compressor` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 141 | `what is the function of the expansion tank in high temperature jacket water cooling?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=14); fast-path active (0.00s rewrite) |
| 142 | `how does the automatic deaerating valve protect boiler economizer from oxygen pitting?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 143 | `explain how governor droop setting ensures proportional load sharing between generators` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 144 | `what are the safety interlocks on marine auxiliary boiler automated burner control?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 145 | `how to test high bilge level alarm sensors in auxiliary machinery spaces?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 146 | `explain the working of thermostatic expansion valve in provisions refrigeration plant` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 147 | `what causes starting air pipe explosion on main engine air distributor line?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 148 | `how does the shaft grounding device protect main engine bearings from electrical erosion?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 149 | `what is the procedure for draining scavenge air receiver underpiston sludge spaces?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 150 | `explain the operation of the emergency fire pump sea chest suction priming ejector` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 151 | `what are the symptoms of air leakage into vacuum condenser of fresh water generator?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=14); fast-path active (0.00s rewrite) |
| 152 | `how does the hydraulic telemotor system transmit helm command to rudder steering gear?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 153 | `explain how differential pressure transmitters measure cargo tank level by bubbler gauge` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 154 | `what is the function of the main engine cylinder lubrication timed electronic lubricator?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 155 | `how to blow down boiler gauge glass safely under high steam operating pressure?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 156 | `what causes turbocharger surging when vessel accelerates in rough weather conditions?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 157 | `how does the deck water seal prevent hydrocarbon gas backflow from cargo tanks?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 158 | `explain the procedure for synchronizing two alternators using dark lamp method` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 159 | `what are the dangers of entering enclosed chain locker without atmospheric testing?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 160 | `how to inspect main engine crosshead slipper guide clearances during drydock?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 161 | `explain the working principle of oily water separator coalescer filtering elements` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=11); fast-path active (0.00s rewrite) |
| 162 | `what is the purpose of the pressure vacuum relief valve on chemical cargo tanks?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=14); fast-path active (0.00s rewrite) |
| 163 | `how does the stern tube lip seal prevent lubricating oil leakage into seawater?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 164 | `what are the regulatory requirements for testing steering gear 12 hours before departure?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=13); fast-path active (0.00s rewrite) |
| 165 | `explain the action of cathodic protection impressed current system on ship hull` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=12); fast-path active (0.00s rewrite) |
| 166 | `what is the function of the relief valve fitted on cylinder head indicator cock?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=14); fast-path active (0.00s rewrite) |
| 167 | `how to change over heavy fuel oil to marine gas oil before entering ECA area?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=15); fast-path active (0.00s rewrite) |
| 168 | `explain the working of the salinometer temperature compensation thermistor bridge` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=10); fast-path active (0.00s rewrite) |
| 169 | `what are the causes of high crankcase pressure in a 4-stroke marine diesel engine?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=14); fast-path active (0.00s rewrite) |
| 170 | `how does the bilge injection valve use main seawater cooling pump in emergency flooding?` | `FAST_PATH_MARINE` | `FAST_PATH_MARINE` | [PASS] | Direct standalone marine query (words=14); fast-path active (0.00s rewrite) |

### Category 6: Maritime Typos (35 Queries)

| ID | Query | Expected Routing | Actual Routing | Status | Notes / Rationale |
| :---: | :--- | :--- | :--- | :---: | :--- |
| 171 | `tell me about auxilery engin` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'auxilery' -> 'Auxiliary' |
| 172 | `explain stearng systm safety` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'stearng' -> 'Steering' |
| 173 | `how does puryfyer seperate watter?` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'puryfyer' -> 'Purifier' |
| 174 | `tell me about boiller saftey valfe` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'boiller' -> 'Boiler' |
| 175 | `what is navigaton equpment on ship?` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'navigaton' -> 'Navigation' |
| 176 | `explain refrigiration comprosser cycle` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'refrigiration' -> 'Refrigeration' |
| 177 | `how does proppeler cavitaton occur?` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'proppeler' -> 'Propeller' |
| 178 | `tell me about scavange manifold fier` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'scavange' -> 'Scavenge' |
| 179 | `what is turbockarger surging cause?` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'turbockarger' -> 'Turbocharger' |
| 180 | `how does lubrecaton oyl pump operate?` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'lubrecaton' -> 'Lubrication' |
| 181 | `explain balast watr treatmnt systm` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'balast' -> 'Ballast' |
| 182 | `tell me about incenerator garbage burning` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'incenerator' -> 'Incinerator' |
| 183 | `what is evaperator fresh watr generator?` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'evaperator' -> 'Evaporator' |
| 184 | `how does air comprosser charge bottels?` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'comprosser' -> 'Compressor' |
| 185 | `explain govenor speed droop regulaton` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'govenor' -> 'Governor' |
| 186 | `tell me about crankshft bearing clearence` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'crankshft' -> 'Crankshaft' |
| 187 | `what is condensor vacuum ejector problem?` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'condensor' -> 'Condenser' |
| 188 | `how does intercoler cool scavange air?` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'intercoler' -> 'Intercooler' |
| 189 | `explain soundng pipe watter finding paste` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'soundng' -> 'Sounding' |
| 190 | `tell me about manfold pressure gauge` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'manfold' -> 'Manifold' |
| 191 | `what is shakle safe working load rating?` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'shakle' -> 'Shackle' |
| 192 | `how does fairled roller mooring guide line?` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'fairled' -> 'Fairlead' |
| 193 | `tell me about liferafft hydrostatc release` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'liferafft' -> 'Liferaft' |
| 194 | `explain economezer exhaust gas cleaning` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'economezer' -> 'Economizer' |
| 195 | `what is superchargr turbine wheel blade?` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'superchargr' -> 'Supercharger' |
| 196 | `how does oilly watter separater alarm trip?` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'watter' -> 'Water' |
| 197 | `tell me about inertt gas generater plant` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'inertt' -> 'Inert' |
| 198 | `explain crude oyl washng procidure` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'washng' -> 'Washing' |
| 199 | `what is bilgge water pump strainer box?` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'bilgge' -> 'Bilge' |
| 200 | `how does seperaator bowl disk stack clean?` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'seperaator' -> 'Separator' |
| 201 | `tell me about energency stearing local lever` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'stearing' -> 'Steering' |
| 202 | `explain saftey valfe steam popping setting` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'saftey' -> 'Safety' |
| 203 | `what is actautor pneumatic air supply pressure?` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'actautor' -> 'Actuator' |
| 204 | `how does lifebote gravity davit winch lower?` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'lifebote' -> 'Lifeboat' |
| 205 | `tell me about gyrocumpass repeater master unit` | `TYPO_DETECTED` | `TYPO_DETECTED` | [PASS] | Typo detected: 'gyrocumpass' -> 'Gyrocompass' |

### Category 7: Multi-Turn Pronoun (35 Queries)

| ID | Query | Expected Routing | Actual Routing | Status | Notes / Rationale |
| :---: | :--- | :--- | :--- | :---: | :--- |
| 206 | `what if it fails completely?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 207 | `can that happen suddenly while sailing?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 208 | `is it mandatory under maritime law?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 209 | `what about during severe heavy weather?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 210 | `how often should we inspect this onboard?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 211 | `what are those consequences if ignored?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 212 | `explain the third step in greater detail` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 213 | `what should i do next after acknowledging alarm?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 214 | `why did you recommend that specific valve?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 215 | `tell me more about its internal construction` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 216 | `continue explaining the emergency phase` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 217 | `how does the second one compare to the first?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 218 | `where are they stored on cargo ships?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 219 | `who is officially responsible for them?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 220 | `can you summarize the previous points?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 221 | `is that applicable to oil tankers as well?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 222 | `what causes its outlet temperature to increase?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 223 | `how do they prevent accidental discharge overboard?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 224 | `what about point 2 you mentioned earlier?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 225 | `why does this occur only at full sea speed?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 226 | `explain more about the testing frequency` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 227 | `what else could be causing this abnormal pressure?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 228 | `what next if reset does not work?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 229 | `and what about the auxiliary diesel generator?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 230 | `how come it was not detected during survey?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 231 | `can these two systems operate simultaneously?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 232 | `what happens after step 4 in the checklist?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 233 | `who should be notified immediately about this?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 234 | `is this required under solas or marpol?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 235 | `how to inspect it safely without stopping main engine?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 236 | `what are the risks if we ignore that warning?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 237 | `why does that valve fail more often than others?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 238 | `tell more details regarding calibration procedures` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 239 | `how does the former differ from the latter?` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |
| 240 | `continue to the next section of the regulations` | `COREFERENCE_REWRITE` | `COREFERENCE_REWRITE` | [PASS] | Contains pronoun/coreference/followup; fast-path skipped, forwarded to LLM Query Rewrite |

### Category 8: Deceptive Off-Topic (25 Queries)

| ID | Query | Expected Routing | Actual Routing | Status | Notes / Rationale |
| :---: | :--- | :--- | :--- | :---: | :--- |
| 241 | `how does a jet engine afterburner generate supersonic thrust?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 242 | `what are the hyperparameters for random forest machine learning models?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 243 | `how to perform laparoscopic appendectomy in general surgery` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 244 | `explain the monetary policy transmission mechanism of the federal reserve` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 245 | `how to calibrate guitar amplifier tube bias voltage with multimeter` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 246 | `what causes engine knocking in a four cylinder honda civic automobile?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 247 | `how to implement jwt token authentication in a react native application` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 248 | `who was the second man to walk on the moon during apollo 11?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 249 | `how to diagnose common feline leukemia virus symptoms in domestic cats` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 250 | `what is the recipe for baking authentic napoletana pizza dough with yeast?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 251 | `how to tune drums for recording in a home studio acoustic environment` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 252 | `explain the difference between mitosis and meiosis in human cellular biology` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 253 | `how to invest in index mutual funds and rebalance asset portfolio` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 254 | `who directed the movie the godfather and apocalypse now?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 255 | `how to fix a leaking bathroom toilet flush tank siphon valve` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 256 | `what are the rules for castling in competitive chess tournaments?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 257 | `how to build a docker container image with multi-stage build optimization` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 258 | `what are the clinical stages of parkinson disease in elderly patients?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 259 | `how does the hubble space telescope point toward distant galaxies without thrusters?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 260 | `what is the weather forecast for paris france this weekend?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 261 | `who won the premier league football championship trophy in 2023?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 262 | `how to write a recursive function in python for fibonacci sequence` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 263 | `what are the symptoms of high blood pressure and hypertension?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 264 | `how to train a labrador retriever puppy to stop biting furniture` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 265 | `who was the third prime minister of independent india?` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |

### Category 9: Single-Word Off-Topic (20 Queries)

| ID | Query | Expected Routing | Actual Routing | Status | Notes / Rationale |
| :---: | :--- | :--- | :--- | :---: | :--- |
| 266 | `javascript` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 267 | `bitcoin` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 268 | `cricket` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 269 | `bollywood` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 270 | `recipe` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 271 | `photosynthesis` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 272 | `dinosaur` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 273 | `olympics` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 274 | `minecraft` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 275 | `smartwatch` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 276 | `guitar` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 277 | `piano` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 278 | `parliament` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 279 | `barbell` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 280 | `netflix` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 281 | `iphone` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 282 | `ipad` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 283 | `playstation` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 284 | `airplane` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |
| 285 | `helicopter` | `OFF_TOPIC` | `OFF_TOPIC` | [PASS] | Matched off-topic perimeter guard; zero-hallucination perimeter triggers. |

### Category 10: Persona & Social (15 Queries)

| ID | Query | Expected Routing | Actual Routing | Status | Notes / Rationale |
| :---: | :--- | :--- | :--- | :---: | :--- |
| 286 | `hello dolphin` | `FAST_PATH_SOCIAL` | `FAST_PATH_SOCIAL` | [PASS] | Social/Greeting intent matched (intent=GREETING, greeting=True) |
| 287 | `who are you?` | `FAST_PATH_SOCIAL` | `FAST_PATH_SOCIAL` | [PASS] | Social/Greeting intent matched (intent=GREETING, greeting=False) |
| 288 | `what is your name?` | `FAST_PATH_SOCIAL` | `FAST_PATH_SOCIAL` | [PASS] | Social/Greeting intent matched (intent=GREETING, greeting=False) |
| 289 | `who created you?` | `FAST_PATH_SOCIAL` | `FAST_PATH_SOCIAL` | [PASS] | Social/Greeting intent matched (intent=GREETING, greeting=False) |
| 290 | `who made you?` | `FAST_PATH_SOCIAL` | `FAST_PATH_SOCIAL` | [PASS] | Social/Greeting intent matched (intent=GREETING, greeting=False) |
| 291 | `good morning dolphin` | `FAST_PATH_SOCIAL` | `FAST_PATH_SOCIAL` | [PASS] | Social/Greeting intent matched (intent=GREETING, greeting=True) |
| 292 | `good afternoon officer` | `FAST_PATH_SOCIAL` | `FAST_PATH_SOCIAL` | [PASS] | Social/Greeting intent matched (intent=GREETING, greeting=True) |
| 293 | `good evening captain` | `FAST_PATH_SOCIAL` | `FAST_PATH_SOCIAL` | [PASS] | Social/Greeting intent matched (intent=GREETING, greeting=True) |
| 294 | `how are you today?` | `FAST_PATH_SOCIAL` | `FAST_PATH_SOCIAL` | [PASS] | Social/Greeting intent matched (intent=WELL_WISH, greeting=False) |
| 295 | `how is it going?` | `FAST_PATH_SOCIAL` | `FAST_PATH_SOCIAL` | [PASS] | Social/Greeting intent matched (intent=WELL_WISH, greeting=False) |
| 296 | `thank you for your help` | `FAST_PATH_SOCIAL` | `FAST_PATH_SOCIAL` | [PASS] | Social/Greeting intent matched (intent=THANK, greeting=False) |
| 297 | `thanks a lot dolphin` | `FAST_PATH_SOCIAL` | `FAST_PATH_SOCIAL` | [PASS] | Social/Greeting intent matched (intent=THANK, greeting=False) |
| 298 | `bye dolphin see you tomorrow` | `FAST_PATH_SOCIAL` | `FAST_PATH_SOCIAL` | [PASS] | Social/Greeting intent matched (intent=GOODBYE, greeting=False) |
| 299 | `have a nice day` | `FAST_PATH_SOCIAL` | `FAST_PATH_SOCIAL` | [PASS] | Social/Greeting intent matched (intent=GOODBYE, greeting=False) |
| 300 | `goodbye captain` | `FAST_PATH_SOCIAL` | `FAST_PATH_SOCIAL` | [PASS] | Social/Greeting intent matched (intent=GREETING, greeting=True) |
