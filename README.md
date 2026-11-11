# CloudCost Compare — Cloud Economics Lab 7

**Cloud-Native E-Commerce & Analytics Platform · AWS vs Azure vs GCP**

This repository contains a **Streamlit model**, a pure-Python cost engine, editable price references, tests, a formula-driven baseline workbook, and reproducible sample outputs. It is intended as an interactive Lab 7 learning/submission artifact and is independent of the previous Floci FinOps Explorer project. The bundled XLSX is a **separate baseline worksheet**, not a live synchronization target of Streamlit edits.

> **Pricing disclosure:** all displayed amounts are **modeled budget estimates in USD**, not real AWS/Azure/GCP quotes, not invoices and not live API results. Some included rates are public references while many are provisional planning allowances. A final submission should validate rates and configurations in each provider's **official pricing calculator** and attach calculator screenshots or exports. The project does not require cloud credentials and does not provision real resources.

## 1. Quick start / Windows

1. Unzip the project and open the extracted `CloudCostCompare_Lab7` directory.
2. **Double-click `start_windows.bat`**. The launcher installs Python dependencies, then starts Streamlit.
3. A browser window should open; if not, navigate to `http://localhost:8501`.
4. If Python is not installed, install Python 3.10+ first and reopen the launcher.

**Manual start (PowerShell / Terminal)**

```powershell
cd CloudCostCompare_Lab7
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

On Windows, `py` can replace `python`. On macOS/Linux, use `python3` if necessary.

Stop the server with `Ctrl+C` in the terminal.

## 2. Application pages

| Page | Lab 7 contribution |
|---|---|
| Executive dashboard | Dynamic monthly comparison and cost breakdown; 2/4/10 VM scaling sensitivity |
| Architecture | Equivalent AWS, Azure and GCP component mapping and flow diagram |
| Pricing & evidence | Editable **8-decimal** unit price catalog, URL/verification fields, import/export, service costs |
| Optimization | Six strategies per provider; hypothetical commitment scenario for **base capacity only** |
| Comparative analysis | Pay-as-you-go vs commitments, hidden costs, cost tools, predictability and conditional recommendation |
| Export & submission | Detailed CSVs, English HTML report, official calculator evidence checklist and assignment coverage |

**How to enter prices:** Navigate to **Pricing & evidence**, select a cloud, edit the **USD per unit** column, and press **Apply edited rates**. Tiny values such as `0.00000020` are accepted; the underlying catalog uses 64-bit floating point numbers. Updated rates propagate immediately into all cost reports. Use the `status` field and `source` URL to document a calculator-verified rate.

**How to run what-if scenarios:** Adjust the workload in the sidebar. The page recalculates every cost line and total. The original professor-specified baseline can be restored via **Reset workload to Lab baseline**.

## 3. Mandatory baseline assumptions

| Requirement | Baseline modeled |
|---|---|
| Daily active users | 50,000 |
| API requests | 10,000,000/month |
| Outbound transfer | 1 TiB = **1,024 GiB** / month |
| Object storage | 2 TiB = **2,048 GiB logical**; second region stores another full copy |
| Compute | 2–10 VMs autoscaling; **4 average active**, 730 hours/month |
| Production RDBMS | 2 medium-size instances, one per region; 100 GiB disk each |
| NoSQL | Budget for product catalog and sessions; operations not fixed by professor |
| CI/CD | 10 builds/day for 30 days, **10 minutes per build** |
| Full logging | 100 GiB/month assumed and editable |
| ML recommender | 4 batch hours/day assumed and editable |
| Cross-region data | 100 GiB/month replication allowance, editable |
| Background events | 1,000,000 serverless functions/month (modeling assumption) |
| CDN requests | 2,000,000/month (modeling assumption) |

**Important unit distinction:** 1 TB may mean 1,000 GB in a provider's metering and 1 TiB means 1,024 GiB. The baseline deliberately uses 1,024 GiB for the assignment's 1 TB and 2,048 GiB for its 2 TB. When copying official calculator estimates, use the provider's actual unit convention and update the app assumption if necessary.

Regions in architecture: **AWS:** us-east-1 + us-east-2; **Azure:** East US + East US 2; **GCP:** us-central1 + us-east1. Rates are not promised to be accurate across both regions; verify each region and substitute weighted rates, or add distinct SKUs if necessary.

**Networking:** Public internet egress is counted exactly once under the CDN data transfer line in each cloud. CDN request fees, API requests, DNS, load balancers and separately specified cross-region replication are additional rows.

**Included extra categories:** Analytics and Security/Auth are shown alongside the seven required cost categories. External PCI payment gateway transaction fees are excluded explicitly; the service is represented architecturally but is not zero-cost in production.

## 4. Official calculators (required by Lab 7)

- **AWS** — https://calculator.aws/
- **Azure** — https://azure.microsoft.com/pricing/calculator/
- **GCP** — https://cloud.google.com/products/calculator

Suggested audit procedure:

1. Select the required regions and match the modeled compute SKU (2 vCPU / 8 GiB) plus 2–10 autoscaling assumptions.
2. Include the second region and database replica costs. Check storage **class**, inter-region replication and backup retention.
3. Model 10 million API requests/month, CDN requests and 1 TB of data transfer without counting the same internet egress twice.
4. Include medium production relational + NoSQL DB, 10 builds/day, full log ingestion/retention, and batch recommendation ML.
5. Record monthly per-service prices/quantities in the app, set status to **Calculator-verified** and paste the most specific evidence link available. Take screenshots of calculator outputs (including regions and SKUs).
6. Export **Lab7_Cost_Comparative_Report.html** on the **Export & submission** page and open it in a browser for printing or PDF conversion if requested.
7. Submit app code, exported CSVs, report, and your own evidence screenshots according to professor's actual submission instructions.

**Please do not mislabel the sample reference prices as verified official quotes.** AWS states that its public calculator estimates do not generally include Free Tier. Other tools differ in free grants, negotiated rates, commitments and billing units. Our model excludes free tier, taxes, cloud support plans, payment transaction fees, and negotiated credits.

## 5. How costs are calculated

Each service line is `quantity × rate` in USD/month. The quantity mapping is handled in `cost_engine.usage_quantity()`.

Examples:

- `VM hours = average running VMs × 730`, baseline = `4 × 730 = 2,920 VM-hours`.
- `Replicated object storage = 2,048 GiB × 2 regions = 4,096 GiB-month`.
- `DB compute = 2 replicas × 730 = 1,460 DB-hours`.
- `API request units = 10,000,000 / 1,000,000 = 10 million-request units`.
- `CDN egress = 1,024 GiB` (charged once, assuming CDN serves the internet-facing bytes).
- `Build minutes = 10/day × 30 days × 10 minutes = 3,000 minutes`.
- `ML hours = 4 hours/day × 30 days = 120 hours`.
- `Commitment scenario savings = 2 baseline VMs × 730 hours × applicable unit price × assumed discount`; incremental autoscaled VMs stay at uncommitted rates.

**Simplicity limitations:** Lambda/Azure Functions/GCP functions are budgeted as an illustrative million-event bundle (fixed assumed memory/duration); real invocation and compute/memory billing should be recreated in official calculators. Azure disk costs are a modeled GiB equivalent although Azure disks use tiered SKU sizes. API tiers and log retention may also be nonlinear. The app is intentionally an educational cost model, **not an exact cloud billing emulator**.

## 6. Project files

```text
CloudCostCompare_Lab7/
├── app.py                         # Streamlit UI
├── cost_engine.py                 # Pricing, quantities, totals, reports, architectures
├── pricing_reference.json        # Editable starting service catalog with provenance labels
├── requirements.txt              # Python dependencies
├── start_windows.bat             # Windows double-click launcher
├── README.md                     # This document
├── Lab7_Cloud_Cost_Model.xlsx    # Optional, separate formula-driven baseline workbook
├── .streamlit/config.toml        # App theme
├── tests/test_cost_engine.py     # Pricing and workload tests
└── samples/
    ├── Lab7_sample_report.html
    ├── Lab7_sample_service_costs.csv
    ├── Lab7_sample_comparison.csv
    └── Lab7_sample_optimizations.csv
```

## 7. Automated testing

```shell
python -m unittest discover -s tests -v
```

Tests cover mandatory baseline, arithmetic reconciliation, cloud architecture, tiny unit rates, no duplicate internet egress, 2-region object copies, autoscaling monotonicity, commitment discounts, edit integrity, logging and block-disk sensitivity and report content.

## 8. Suggested evidence screenshots for your submission

Create screenshots *after running the app locally*:

1. **Dashboard:** AWS/Azure/GCP totals and stacked chart.
2. **Architecture:** three-provider matrix and selected architecture diagram.
3. **Pricing:** a service with manually verified unit rate and source URL.
4. **Optimization:** the six strategies for each cloud and base-capacity savings example.
5. **Recommendation:** cost ranking, hidden costs and conditional best-value statement.
6. **Official calculators:** one evidence screenshot/export for each provider showing the final matched estimate.

No screenshots are fabricated in this package.

## 9. Troubleshooting

- **'python' is not recognized:** install Python 3.10+ and select "Add Python to PATH"; then retry.
- **The port 8501 is busy:** Streamlit will usually pick another port; inspect the Local URL shown in the terminal.
- **A tiny unit price won't save:** ensure you're using this Lab 7 `app.py`, not the old Floci app. In **Pricing & evidence** use 8 decimal places and press **Apply edited rates**.
- **Prices reset when the application restarts:** session-state edits are intentionally temporary. Use **Download current pricing catalog (CSV)**, then **Import updated pricing CSV** next time. No files are silently modified on disk.
- **Graph does not display:** refresh the browser; architecture table remains available.
- **Official pricing seems different:** that is expected for provisional rates, currency/region/tier differences, free grants and real time rates; overwrite the catalog with the evidence-backed value.

---

### Assignment coverage

Task 1 — Monthly service and provider totals: dashboard + pricing catalog + sample detailed CSV. **Requires official calculator evidence to finalize.**

Task 2 — Compute, storage, database, networking, DevOps, monitoring, and AI/ML breakdown: dashboard.

Task 3 — At least 5 provider-specific optimizations: six per cloud.

Task 4 — Pricing model comparison, hidden fees, management tools and cost predictability: comparative analysis.

Task 5 — Lowest modeled provider, conditional best value and trade-offs: comparative analysis + exported English report.

## Streamlit Cloud deployment and final assignment comparison (updated)

See [DEPLOY_STREAMLIT.md](DEPLOY_STREAMLIT.md) for deployment instructions. The **Lab 7 final comparison** page is the default and shows the AWS official calculator summary ($1,352.06/month), with Azure ($1,467.05/month) and GCP ($1,217.25/month) estimated using hypothetical category adjustment factors. Those peer totals are not official quotes. This fixed comparison is separate from the existing editable what-if model on the other pages. The original RAR did not include the Windows launcher or tests referenced earlier in this README.
