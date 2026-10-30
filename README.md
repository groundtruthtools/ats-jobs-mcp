# ats-jobs-mcp: Company Facts

<!-- mcp-name: io.github.groundtruthtools/ats-jobs-mcp -->

**An MCP server for company data read from the official or original source.**
Newly formed US businesses straight from state registers, with their website
found only on proof. A company's register entry, tech stack, DNS and email
provider, SEC financials and open jobs, each with a link to where it came from.

The full server runs remotely at **https://companyfacts.dev/mcp** with 20 tools
and nothing to install. This PyPI package is the small local edition: the three
job tools, run on your own machine.

---

## Use it with no install

Point any MCP client that speaks Streamable HTTP at the URL:

```json
{
  "mcpServers": {
    "company-facts": {
      "url": "https://companyfacts.dev/mcp"
    }
  }
}
```

No account and no key: 10 free calls a day. Past that, pay per call with x402
(USDC on Base) or use a prepaid key (see https://companyfacts.dev/pricing).
A call that finds nothing is not charged.

The same tools answer plain HTTP, for agents that do not speak MCP:

- `GET https://companyfacts.dev/openapi.json` for a tool-calling agent
- `GET https://companyfacts.dev/llms.txt` for a model reading the service in prose
- `GET https://companyfacts.dev/v1/new-businesses?states=CO&mode=new`

## Company tools (remote)

| Tool | What it returns |
|---|---|
| `new_businesses` | Newly formed businesses from the official Secretary of State registers of New York, Colorado, Oregon, Connecticut and Pennsylvania, in one record format. Feed by formation date, search by name, or look up by state entity number (KYB checks). Each record carries the company's website when one was found with proof, else says none was found. |
| `company_search` | Search every company we track: filter by state, city, name, formation date, technology on its site (Shopify, WordPress, ...), whether it publishes a phone, role inbox or contact page, and hiring. A search with no match is not charged. |
| `company_lookup` | One company from its domain: registrar, DNS and email provider, website tech stack, hiring from its own job board, plus its official register entry or SEC figures when you give name and country or a ticker. |
| `search_company_registry` | One country's official company register by name (UK, Norway, France, Finland, Czechia, Slovakia, Ireland, Australia, or GLEIF worldwide), in one shape. |
| `sec_financials` | US public company financials from SEC EDGAR XBRL. |
| `validate_vat` | An EU VAT number checked against the European Commission's VIES service. |
| `domain_lookup` | Registration (RDAP), DNS records, email provider, SPF and DMARC for a domain. |
| `detect_tech_stack` | The technologies behind a web page, each with its evidence. |
| `federal_contracts` | Awarded US federal contracts from USAspending. |

Websites are attached to new businesses only on proof: the site's own pages
must show the exact legal name and the same city, state or ZIP as the register.
Records never carry officers, directors, individual registered agents, emails,
phones or street addresses.

## Job tools

| Tool | What it returns |
|---|---|
| `find_company_board` | Which applicant-tracking system a company's careers page runs on, and its board name. |
| `list_open_jobs` | Every open job at one company, read from its own Greenhouse, Ashby, Lever or Workable board. |
| `compare_companies` | Open jobs across up to 20 companies in one schema. |
| `job_changes` | Jobs newly posted, taken down, reopened or edited, day by day, from a daily record of every board. |
| `hiring_summary` | One company's hiring at a glance: roles by department and place, remote share, salary ranges, recent openings and closings. |

The vendors publish open job board APIs, and all of them are useless unless you
already know the company's board name. None publishes a directory of its
customers, so this carries one: 8,532 boards on the remote server, each
confirmed against the vendor's own API.

## Other tools (remote)

`read_page` (a web page or PDF as markdown), `extract_page` (named fields from a
page as JSON, paid only), `check_email` (syntax, mail servers, disposable and
role flags), `search_papers` (OpenAlex), `search_hacker_news`, `app_store_lookup`.

Every tool is read-only and declares a title and `readOnlyHint`.

## Salaries, parsed, and refused when unclear

Ashby prints pay as `"$211.4K - $290.6K"`. Greenhouse prints it in cents,
sometimes as several bands at once. Both are turned into numbers:

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

`salary_text` always keeps what the employer actually wrote.

## No personal data

Recruiter names are never returned. Email addresses and phone numbers are
removed from job descriptions. Unlisted Ashby postings are dropped, because
Ashby's documentation says they should not be shown publicly.

## Or install the local job edition

```bash
pip install ats-jobs-mcp
```

```json
{
  "mcpServers": {
    "ats-jobs": {
      "command": "ats-jobs-mcp"
    }
  }
}
```

The local edition has `find_company_board`, `list_open_jobs` and
`compare_companies` over a bundled directory of 7,479 Greenhouse and Ashby
boards (Lever by name, for example `lever:spotify`). It is free, runs on your
machine, and takes no cut of anything.

## Python and LangChain

- `pip install groundtruth-company`: a Python client for the company tools.
- `pip install langchain-groundtruth`: the same tools as LangChain tools.

## Relation to the Apify Actors

The same job parsing runs as an Apify Actor at
[apify.com/groundtruth/ats-job-listings](https://apify.com/groundtruth/ats-job-listings).
`tests/test_core_parity.py` fails if the two copies of the parsing logic drift
apart.

## Licence

MIT. Job postings belong to the employers who published them. Register records
belong to the states that publish them.
