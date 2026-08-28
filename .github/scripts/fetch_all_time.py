"""Fetch a GitHub user's entire contribution history and emit it in the
gh-space-shooter --raw-input schema (one flat, gap-free grid of weeks)."""
import json, os, sys, datetime, urllib.request

USER = sys.argv[1]
OUT = sys.argv[2]
TOKEN = os.environ["GH_TOKEN"]

API = "https://api.github.com/graphql"
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
          "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def gql(query, variables):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}",
                 "Content-Type": "application/json",
                 "User-Agent": "all-time-contributions"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit("GraphQL: " + "; ".join(e["message"] for e in body["errors"]))
    return body["data"]


YEARS_Q = """
query($u:String!){ user(login:$u){ createdAt
  contributionsCollection{ contributionYears } } }
"""

CAL_Q = """
query($u:String!,$from:DateTime!,$to:DateTime!){
  user(login:$u){ contributionsCollection(from:$from,to:$to){
    contributionCalendar{ totalContributions weeks{ contributionDays{
      date contributionCount contributionLevel } } } } } }
"""

meta = gql(YEARS_Q, {"u": USER})["user"]
years = sorted(meta["contributionsCollection"]["contributionYears"])
created = meta["createdAt"][:10]

# GitHub caps one calendar query at a year, so walk year by year and merge on date.
by_date, total = {}, 0
for y in years:
    data = gql(CAL_Q, {"u": USER,
                       "from": f"{y}-01-01T00:00:00Z",
                       "to": f"{y}-12-31T23:59:59Z"})
    cal = data["user"]["contributionsCollection"]["contributionCalendar"]
    total += cal["totalContributions"]
    for week in cal["weeks"]:
        for d in week["contributionDays"]:
            by_date[d["date"]] = {"date": d["date"],
                                  "count": d["contributionCount"],
                                  "level": LEVELS.get(d["contributionLevel"], 0)}

# Trim to the account's real lifetime, then pad out to whole Sun-Sat weeks
# so every column the renderer draws is a full seven cells.
today = datetime.date.today().isoformat()
days = sorted(d for d in by_date if created <= d <= today)
start = datetime.date.fromisoformat(days[0])
end = datetime.date.fromisoformat(days[-1])
start -= datetime.timedelta(days=(start.weekday() + 1) % 7)   # back to Sunday
end += datetime.timedelta(days=(5 - end.weekday()) % 7)       # on to Saturday

weeks, cur = [], []
day = start
while day <= end:
    cur.append(by_date.get(day.isoformat(),
                           {"date": day.isoformat(), "count": 0, "level": 0}))
    if len(cur) == 7:
        weeks.append({"days": cur})
        cur = []
    day += datetime.timedelta(days=1)

out = {"username": USER, "total_contributions": total, "weeks": weeks}
with open(OUT, "w") as f:
    json.dump(out, f)

alive = sum(1 for w in weeks for d in w["days"] if d["level"] > 0)
print(f"years {years[0]}-{years[-1]}  weeks {len(weeks)}  "
      f"days {len(weeks)*7}  contributions {total}  lit cells {alive}")
print(f"range {weeks[0]['days'][0]['date']} .. {weeks[-1]['days'][-1]['date']}")
