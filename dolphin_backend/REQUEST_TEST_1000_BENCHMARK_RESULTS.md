# 1,000-Query Comprehensive Retrieval Benchmark Report

## 1. Executive Summary

| Metric | Result |
| :--- | :--- |
| **Total Queries Evaluated** | **1024** |
| **Total Passed (✅)** | **999 (97.6%)** |
| **Total Failed (❌)** | **25 (2.4%)** |
| **Total Execution Time** | **829.19 seconds** |
| **Average Query Latency** | **809.8 ms** |

## 2. Category Accuracy Breakdown

| Category | Total Queries | Passed (✅) | Failed (❌) | Accuracy (%) |
| :--- | :---: | :---: | :---: | :---: |
| **Category 1: Abbreviations (Inside & Outside)** | 212 | 204 | 8 | **96.2%** |
| **Category 2: Full-Form Expansions** | 212 | 212 | 0 | **100.0%** |
| **Category 3: Specific Questions in Topic** | 200 | 198 | 2 | **99.0%** |
| **Category 4: Specific Questions Inside Abbr** | 200 | 197 | 3 | **98.5%** |
| **Category 5: Date, Month & Year Regulatory** | 200 | 188 | 12 | **94.0%** |

## 3. Scope of Categories Evaluated

- **Category 1: Abbreviations (Inside & Outside Dictionary)**: Evaluated short-form maritime acronyms (e.g., ECDIS, EGCS, OMM, SECP, OWS, EEBD, SCBA, BWMS, SCR, VLSFO, ARPA, AIS, BNWAS, VDR, GMDSS, EPIRB, SART, LSA, FFA, HRU, PTW, IGS, COW, CPP, SOLAS, MARPOL, STCW, ISM, ISPS, MLC, PSC, CBA, DPA, SSO, etc.).
- **Category 2: Full-Form Abbreviation Expansions**: Evaluated complete technical expansions (e.g., Electronic Chart Display and Information System, Onboard Monitoring Manual, Scrubber Emission Control Plan, Ship Energy Efficiency Management Plan, Oily Water Separator, etc.).
- **Category 3: Specific Questions in Topic**: Evaluated operational questions across marine machinery, safety precautions, maintenance, and navigation principles.
- **Category 4: Specific Questions Inside Abbreviations**: Evaluated sub-parameters, alarm thresholds, zero/span calibration intervals, and sensor limits inside specific equipment.
- **Category 5: Date, Month & Year Regulatory Questions**: Evaluated temporal regulations and compliance timelines (e.g., gas meters effective January 2026, fuel consumption reporting 2026, IMO 2020 sulfur cap, CII/EEXI deadlines, etc.).

## 4. Root-Cause Analysis of Unmatched Queries

A total of 25 queries did not match strict keywords:

| # | Category | Query | Retrieved Topic | Reason |
| :---: | :--- | :--- | :--- | :--- |
| 88 | Category 1: Abbreviations (Inside & Outside) | What is RCDS? | RCC | Retrieved 'RCC' lacks keywords ['raster', 'chart', 'display'] |
| 103 | Category 1: Abbreviations (Inside & Outside) | NBDP | N | Retrieved 'N' lacks keywords ['narrow', 'band', 'direct'] |
| 104 | Category 1: Abbreviations (Inside & Outside) | What is NBDP? | N | Retrieved 'N' lacks keywords ['narrow', 'band', 'direct'] |
| 130 | Category 1: Abbreviations (Inside & Outside) | What is FRC? | F | Retrieved 'F' lacks keywords ['fast', 'rescue', 'craft'] |
| 133 | Category 1: Abbreviations (Inside & Outside) | FFE | F | Retrieved 'F' lacks keywords ['fire', 'fighting', 'equipment'] |
| 134 | Category 1: Abbreviations (Inside & Outside) | What is FFE? | F | Retrieved 'F' lacks keywords ['fire', 'fighting', 'equipment'] |
| 209 | Category 1: Abbreviations (Inside & Outside) | IAPPC | IAPH | Retrieved 'IAPH' lacks keywords ['air', 'pollution', 'prevention'] |
| 210 | Category 1: Abbreviations (Inside & Outside) | What is IAPPC? | IAPH | Retrieved 'IAPH' lacks keywords ['air', 'pollution', 'prevention'] |
| 532 | Category 3: Specific Questions in Topic | Troubleshooting and safety guidelines for hydrophobic bilge filter replacement and maintenance | DBMS-608-Engineroom Pipes and Pumping Systems | Retrieved 'DBMS-608-Engineroom Pipes an' lacks keywords ['bilge', 'filter', 'hydrophobic'] |
| 534 | Category 3: Specific Questions in Topic | Chief Engineer checklist for hydrophobic bilge filter replacement and maintenance | Checklist for maintenance of pollution equipment | Retrieved 'Checklist for maintenance of' lacks keywords ['bilge', 'filter', 'hydrophobic'] |
| 658 | Category 4: Specific Questions Inside Abbr | Port State Control PSC inspection checklist for what are Scheme A vs Scheme B approval requirements in SECP? | PSC | Retrieved 'PSC' lacks keywords ['scheme a', 'scheme b', 'secp'] |
| 688 | Category 4: Specific Questions Inside Abbr | Port State Control PSC inspection checklist for how often must hydrostatic release unit HRU be replaced on liferafts? | Preventing Detentions | Retrieved 'Preventing Detentions' lacks keywords ['hru', 'hydrostatic release', 'liferaft'] |
| 696 | Category 4: Specific Questions Inside Abbr | Detailed regulatory guidance: what is the UV radiation dose threshold for organism neutralization in BWMS? | BWM -Possible Treatment Methods | Retrieved 'BWM -Possible Treatment Meth' lacks keywords ['uv', 'radiation', 'dose'] |
| 922 | Category 5: Date, Month & Year Regulatory | Summary of changes effective dates and grandfather clauses for what are the new lifting appliance and anchor handling winch rules effective 2026? | Changes in the Rules and Regulations for the Construction and Classification of Steel Ships | Retrieved 'Changes in the Rules and Reg' lacks keywords ['lifting appliance', 'winch', '2026'] |
| 933 | Category 5: Date, Month & Year Regulatory | What equipment upgrades are mandated prior to what are the revised IMO MEPC 80 greenhouse gas strategy targets for 2030 and 2050?? | Summary Points and Issues to consider | Retrieved 'Summary Points and Issues to' lacks keywords ['mepc 80', 'greenhouse gas', '2030'] |
| 937 | Category 5: Date, Month & Year Regulatory | IMO circulars and resolution implementation dates for what are the EU ETS maritime emission trading system phase in deadlines for 2024 to 2026? | MARPOL | Retrieved 'MARPOL' lacks keywords ['eu ets', 'emissions trading', '2024'] |
| 938 | Category 5: Date, Month & Year Regulatory | Flag state enforcement and survey deadlines regarding what are the EU ETS maritime emission trading system phase in deadlines for 2024 to 2026? | EU Regulations | Retrieved 'EU Regulations' lacks keywords ['eu ets', 'emissions trading', '2024'] |
| 940 | Category 5: Date, Month & Year Regulatory | Auditor checklist and penalties for non-compliance with what are the EU ETS maritime emission trading system phase in deadlines for 2024 to 2026? | Regional and Local Regulations | Retrieved 'Regional and Local Regulatio' lacks keywords ['eu ets', 'emissions trading', '2024'] |
| 942 | Category 5: Date, Month & Year Regulatory | Summary of changes effective dates and grandfather clauses for what are the EU ETS maritime emission trading system phase in deadlines for 2024 to 2026? | EU Regulations | Retrieved 'EU Regulations' lacks keywords ['eu ets', 'emissions trading', '2024'] |
| 944 | Category 5: Date, Month & Year Regulatory | How to prepare vessel survey and certificate endorsements for what are the EU ETS maritime emission trading system phase in deadlines for 2024 to 2026?? | Survey and Certification for Environmental Regulations | Retrieved 'Survey and Certification for' lacks keywords ['eu ets', 'emissions trading', '2024'] |
| 952 | Category 5: Date, Month & Year Regulatory | Summary of changes effective dates and grandfather clauses for what are the FuelEU Maritime greenhouse gas intensity reduction targets effective 2025? | Post-operation Feedback and Continuous Improvement | Retrieved 'Post-operation Feedback and ' lacks keywords ['fueleu', 'maritime', '2025'] |
| 997 | Category 5: Date, Month & Year Regulatory | IMO circulars and resolution implementation dates for what were the amendments to MARPOL Annex V regarding cargo residues effective 2018? | MARPOL | Retrieved 'MARPOL' lacks keywords ['marpol annex v', 'garbage', 'cargo residues'] |
| 1002 | Category 5: Date, Month & Year Regulatory | Summary of changes effective dates and grandfather clauses for what were the amendments to MARPOL Annex V regarding cargo residues effective 2018? | MARPOL | Retrieved 'MARPOL' lacks keywords ['marpol annex v', 'garbage', 'cargo residues'] |
| 1004 | Category 5: Date, Month & Year Regulatory | How to prepare vessel survey and certificate endorsements for what were the amendments to MARPOL Annex V regarding cargo residues effective 2018?? | Certificate Requirements for US Flag Vessels | Retrieved 'Certificate Requirements for' lacks keywords ['marpol annex v', 'garbage', 'cargo residues'] |
| 1021 | Category 5: Date, Month & Year Regulatory | Impact of what are the upcoming IMO carbon intensity verification rules for SEEMP Part III in 2026? on ship machinery and instrumentation | Energy Efficiency and IMO | Retrieved 'Energy Efficiency and IMO' lacks keywords ['seemp', 'carbon intensity', '2026'] |
