# ats-jobs-mcp

<!-- mcp-name: io.github.groundtruthtools/ats-jobs-mcp -->

**An MCP server for open job postings, read first-hand from the applicant-tracking
system behind a company's careers page.** Ask your assistant what Anthropic is
hiring for and get the answer from Anthropic's own board, not from a job
aggregator's index.

Built on the job board APIs that Greenhouse, Ashby and Lever publish so third
parties can build job sites. No scraping, no API key, no account, no personal
data.

---

## Why this exists

Those APIs are open, documented, and **useless unless you already know the
company's board name**: that Anthropic's is `anthropic`, Ramp's is `ramp`,
Mistral's is `mistral.ai`.

**None of the vendors publishes a directory of its customers**, and none could,
since no vendor knows about the others. Checked 2026-08-24: `sitemap.xml` on
job-boards.greenhouse.io, boards.greenhouse.io, jobs.lever.co and
apply.workable.com all 404 or redirect.

So this ships one: **7,479 company boards**, every one confirmed against the
vendor's own API, each carrying the date it was confirmed.

## Three tools

### `find_company_board` — which system is a company on?

Give it a company name. Get the system and the board name, plus how many roles
were open when the board was last confirmed.

### `list_open_jobs` — every open role at one company

Title, department, location, employment type, workplace type, posted date, a
parsed salary range where the employer publishes one, and a `verify_url`
pointing at the employer's own advert.

### `compare_companies` — several companies, one schema

The thing no single vendor can do. Companies on Greenhouse and companies on
Ashby come back with the same field names, so they can be compared directly.
One company failing does not lose the others.

## Salaries, parsed, and refused when unclear

Ashby prints pay as `"$211.4K - $290.6K"`. Greenhouse prints it in cents,
sometimes as several bands at once. Neither is filterable, so both are turned
into numbers:

```json
"salary_min": 211400.0, "salary_max": 290600.0,
"salary_currency": "USD", "salary_text": "$211.4K - $290.6K"
```

The parser refuses more often than it guesses, deliberately:

- `$50 - $80 / hour` gives **no salary**. An hourly rate is a different
  quantity and reporting it as annual would be a confident lie.
- `600 000 kr` gives **no salary**. `kr` is Swedish, Norwegian *and* Danish.
- `0.5% - 1.75% - Offers Equity` gives **no salary**. Equity is not pay.
- Bands in two currencies are never spanned into a range that exists nowhere.

`salary_text` always keeps what the employer actually wrote, so nothing is
lost when the parser declines.

Every parsed figure is tested against the employer's own structured
`baseSalary` block, the one published for Google to index — not against a
number someone typed into a test.

## No personal data

Recruiter names are never returned. Email addresses and phone numbers are
**removed from job descriptions**, because descriptions genuinely carry them
and a column of work addresses is a marketing list rather than a job feed.

Unlisted Ashby postings are dropped, because Ashby's documentation says
plainly that they should not be shown publicly.

## Coverage, stated honestly

| System | Boards in the directory |
|---|---:|
| Greenhouse | 4,168 |
| Ashby | 3,311 |

Lever is readable but has almost no boards in the directory yet, so name it
directly (`lever:spotify`) or pass its careers URL. Workable has a confirmed
endpoint but no adapter yet, so it is not listed at all: a directory entry for
something nothing can read is a broken promise.

## Install

```bash
pip install ats-jobs-mcp
```

Then add to your MCP client configuration:

```json
{
  "mcpServers": {
    "ats-jobs": {
      "command": "ats-jobs-mcp"
    }
  }
}
```

## Relation to the hosted version

The same parsing runs as an Apify Actor at
[apify.com/groundtruth/ats-job-listings](https://apify.com/groundtruth/ats-job-listings),
which adds scheduling and an incremental mode that returns only postings you
have not been sent before. This server is free, runs on your machine, and
takes no cut of anything.

`tests/test_core_parity.py` fails if the two copies of the parsing logic drift
apart.

## Licence

MIT. Job postings belong to the employers who published them.
