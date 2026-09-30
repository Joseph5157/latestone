# Client Database Clarification — Business Decisions Needed

## Purpose

We have finished a read-only review of the RTL SQL Server database. It answered most of our technical questions, and we have not changed anything in it. The questions below are the ones only the business can answer.

No database change is requested. Nothing will be modified until we send a separate proposal and you approve it.

## What we now know

- 339 RTLs are currently registered.
- 185 of them are currently linked to a transformer.
- 111 registered RTLs have dated activity in 2026, up to the latest data we can see (17 September 2026).
- None of the 154 registered RTLs without a transformer link has dated 2026 activity.
- Temperature is the only continuous measurement in the database.
- Reporting intervals have historically been 1 hour, 6 hours and 24 hours.
- The database records historical alarms and events. It has no acknowledgement or resolution, and no dependable current Online/Offline status.
- Times are read as South African Standard Time. Temperatures are shown exactly as received.

## Questions

### 1. Which RTLs should we treat as in service?

Being registered does not tell us whether an RTL is in service.

- Should all 339 registered RTLs be treated as monitored?
- If not, which states do you use (for example not yet installed, temporarily out of service, retired)?
- Where is that state kept today?
- Should a retired RTL be marked as retired rather than removed?

### 2. When is an RTL Online, Late or Offline?

The database has no dependable Online/Offline status, so the application has to work it out.

- What counts as the RTL having reported in: a temperature reading, a check-in message, or either?
- After how long without a report is an RTL Late, and after how long Offline? We have only heard "a few hours".
- Should the reporting interval (1, 6 or 24 hours) change those times?
- How should a power-down be treated?
- What counts as back online?

### 3. Is the TUG list the official transformer list?

The TUG report holds about 70,700 transformer records with their place in the hierarchy (Operating Unit, Zone, Sector, CNC, Feeder).

- Is it the approved source for transformers and their hierarchy?
- Is the location number on each record a permanent identifier?
- How often is it refreshed?
- How do you show a transformer that has been decommissioned?

### 4. How should people sign in?

The database holds people and the roles Administrator, Technician and General User, but no usable sign-in details.

- How should each role sign in (for example company single sign-on or a password)?
- Who creates, activates and disables accounts?
- Is there a policy on passwords or sessions that we must follow?

### 5. How are technicians assigned to RTLs?

- Can one RTL have more than one technician?
- Can one technician look after many RTLs?
- When an RTL is reassigned, should we keep the earlier assignments?
- What may an assigned technician do that others cannot?

### 6. What does "Program RTL" do?

Past records show that the transformer code and reporting interval were set on RTLs. The database does not show how, or whether each attempt worked.

- Should the new application send the settings to the RTL itself, or only record a request for another system to carry out?
- If it sends them, by what route (for example SMS)?
- Who may change the reporting interval, and to which values?

### 7. Who is notified, and how?

- Who should receive alerts, and by which channels?
- Who sets up recipients?
- What consent, privacy and retention rules apply to contact details?

### 8. What happens when an alarm occurs?

The database records that a high-temperature or other event happened. It does not record that anyone saw it, dealt with it or cleared it.

- Which events need someone to act (high temperature, sensor error, battery low, power-down)?
- Should the application let users acknowledge, resolve, comment on and escalate them?
- How long should these records be kept?

### 9. Two different temperatures at the same moment

Sometimes the same RTL has two different temperatures recorded at exactly the same time. Today we show that as unclear and pick neither.

- Should we keep showing it as unclear, or is there a rule that decides which reading to use?

### 10. Unusual temperature values

The data contains values such as repeated 0 and 85, values of 160 or more, and a highest value of 493. We show them as received.

- Are these real readings or known bad data?
- Should any be flagged or hidden?

### 11. Other measurements

The current dashboard also shows voltage, current, active power, reactive power, power factor, frequency and energy. The database holds none of them.

- Is there another database, service or device feed that provides them?
- If not, we propose to remove them from the production dashboard instead of showing invented values. Do you agree?

## What happens next

1. We finish mapping the application onto the existing database.
2. We identify only what is genuinely missing.
3. We send a separate change proposal with a reason for each item.
4. Nothing in the database is changed until you approve it.
