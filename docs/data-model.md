# KRW Data Model (reference)

The semantic model behind KRW's existing Power BI / ThoughtSpot, provided 2026-07-05. This is the real vocabulary the custom build must reproduce, and it partially answers **O-2** (see the gap section below). Faithful capture, organized by the role each table plays; measure *definitions* (the DAX/worksheet formulas) were not included and are still needed.

## What this is, and isn't

`_KPIs` and `_Measures` are **computed measure tables** — business metrics derived on top of the physical data (Power BI DAX / ThoughtSpot worksheet measures), not columns we can `SELECT`. The other tables are the **physical source** (or close to it) that our `DataSource` reads and that the semantic layer's SQL is written against. So this gives us the metric vocabulary and the table/column structure; it does **not** give us the formulas, which we must re-express in SQL.

The domain is a legal **referral / mass-tort** practice: referral leads (cancer confirmation, referral firms, fees), a medical intake funnel (`XRay → B-Read → Voucher → Bank Complete`), a call center (calls, answer/wait/duration, agent conversion), and marketing spend by market with TV spot economics.

## Source tables (physical — what the DataSource reads)

- **cases** — lead/case records. `LeadId`, `CaseType`, `Status`, `Milestone`, `Assignee`, `Owner`, `Source_Name`, `source_category`, `primary_contact_type`, contact fields (`Contact_*`: gender, age, language, marital status, nature, phones), `BestPhone`, `CreateDate`, `UpdateDate`, `metadata_*`.
- **referral_leads** — the referral book of business. `LeadId`, `FirstName`/`LastName`, `Gender`, `Age`, `MaritalStatus`, `State`/`State_Name`/`County`/`City`/`City_State`, `CaseType`, `source_category`, `CreateDate`, `LeadCreatedDate_Excel`, `CurrentStatus`, `CurrentMilestone`, `LeadProgress`, cancer fields (`cancer_confirmed`/`CancerConfirmed`/`CancerType`/`WhatIsTheCancerType`/`ImpairmentLevel`), referral-firm economics (`ReferralFirm_Excel`/`_History`, `ReferralFirmFeeAmount_Excel`, `ReferralFirmStatus_Excel`, `OurFirmFeeAmount_Excel`, `EstimatedCaseValue_Excel`, `firm_match`), `ReferralDate`, `voucher_date`/`voucher_signal`, `days_lead_to_referral`, `came_back_flag`/`_reason`, `is_deceased`, `Tags`, `lat`/`lon`, `history_*`, `loaded_at`.
- **stages** — milestone completion per lead. `LeadId`, `StageName`, `StageOrder`, `Lead_stage`, `DateCompleted`, `milestone_complete`, `metadata_*`.
- **referral_stages** — referral funnel completion. `LeadId`, `StageName`, `Ordered_StageName`, `StageOrder`, `DateCompleted`, `milestone_complete`, `loaded_at`.
- **referral_stage_durations** — time-in-stage. `LeadId`, `StageName`, `Ordered_StageName`, `StageOrder`, `DaysToStage`, `DaysInStage`, `DateCompleted`, `PreviousStageCompleted`, `loaded_at`.
- **agent_stats** — weekly call-center agent performance. `agent_ext_id`, `agent_name`, `region`, `week_start`/`week_end`, `leads_contacted`, `leads_converted`, `conversion_rate_pct`, `metadata_loaded_at`.
- **geo** — lead geography. `LeadId`, `City`/`City_State`/`County`/`State`/`State_Name`/`Zip`, `lat`/`lon`, `metadata_loaded_at`.
- **marketing_budget** — spend by market. `date`, `city_code`/`city_state`/`state`, `Budget per Market`, `sheet`.

## Dimension / helper tables

- **DimDate** — primary date dimension. `Date`, `Day`, `WeekStart`, `MonthStart`/`MonthName`/`MonthNo`, `Quarter`/`QuarterStart`, `Year`, `YearMonth`, `YearQuarter`, plus `Date Range` measure.
- **referral_date** — separate date dimension for referral events (same shape, `Ref Date Range` measure). Note there are two date roles (lead date vs referral date).
- **Trend Level / Trend Levels** — field-parameter helper tables (disconnected) that drive the trend-grain selector in the report; not data.

## Measures (business metrics — names/intent; formulas TBD)

Headline KPIs (`_KPIs`): Leads, Marketing Spend, Revenue KPIs, ROAS KPI, Agent Conversion, Voucher.

Full measure set (`_Measures`), grouped:

- **Volume / spend:** Total Leads, Leads, Total Calls, Inbound/Outbound Calls, Total Spend, Marketing Spend, Total Spot Count, Avg Cost per Spot.
- **Efficiency / economics:** Cost per Lead, ROAS, Revenue, Revenue KPI, Avg Case Fee, Answer Rate %, Call to Lead Rate %.
- **Conversion / funnel:** Leads Contacted/Converted, Agent Conversion Rate %, Avg/Top Agent Conversion Rate %, Bank Complete Rate %, Voucher Rate %, XRay Rate %, Leads Reached {XRay, B-Read, Voucher, Bank Complete, Bank Incomplete, Sched for Clinic}.
- **Cycle time:** Avg Days to {XRay, B-Read, Voucher, Bank Complete}, Avg Days in {XRay, B-Read, Voucher} Stage, Avg Days Lead to Bank Complete, Avg Call Duration, Avg Wait Time.
- **Trends (period-over-period):** MTD/YTD/Prior-Week/Prior-Month variants and WoW/MoM % + change for Leads, Calls, Vouchers, Marketing Spend, Revenue KPI, ROAS.
- **Call center:** Calls Answered, Calls Linked to Lead, Queue Routed Calls, Spam Calls, Avg Wait Time, Avg Call Duration.

## What this answers, and the remaining gap

**Answers (O-2, structurally):** the physical tables and columns, the metric vocabulary, the date dimensions, the funnel stages, and the grains. This is enough to draft the semantic registry's tables/dimensions and the *list* of metrics.

**Still needed before the semantic layer is real:**
1. **Measure definitions** — the DAX/SQL formulas behind the `_Measures` (e.g. exactly how `Cost per Lead`, `ROAS`, `Vouchers WoW %`, `Bank Complete Rate %` are computed), so ours match KRW's numbers. Names alone risk subtly wrong metrics.
2. **Which of these are queryable SQL objects** (tables vs views vs Power-BI-only computed tables) and their real schema/object names — plus the **read-only credential** and edition (still **O-1**).
3. Confirmation of the two date roles (lead vs referral) and which drives the MVP visuals.

## Mapping to the MVP's nine visuals (proposed, to confirm)

- **New leads** → `Total Leads` / `Leads` (from `cases` or `referral_leads`, over `DimDate`).
- **Signed cases** → a funnel milestone — likely `Leads Reached Bank Complete` / `Vouchers` (confirm what "signed" means for KRW).
- **Cost per lead** → `Cost per Lead`.
- **Marketing spend** → `Marketing Spend` / `Total Spend` (`marketing_budget`).
- **Leads by week** → `Leads` grouped by `DimDate.WeekStart`.
- **Leads by channel** → group by `cases.source_category` / `Source_Name`.
- **Lead → signed funnel** → `Leads Reached {XRay, B-Read, Voucher, Bank Complete}` (`referral_stages`).
- **Top regions** → `geo` / `referral_leads` `State`/`City`/`County` (nationwide, not TX-only as the mockup implied — confirm).
- **Recent intakes** → recent `cases` by `CreateDate` with `Status`/`Milestone`.
