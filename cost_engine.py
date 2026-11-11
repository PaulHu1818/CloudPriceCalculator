"""Pure-Python pricing model used by the Lab 7 Streamlit app.

All rates are editable USD budget inputs, NOT live guaranteed vendor quotes.
No network calls. A single internet-egress line is charged per provider.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from html import escape
from io import StringIO
import json
from pathlib import Path
from typing import Mapping
import pandas as pd

PROVIDERS = ("AWS", "Azure", "GCP")
CATEGORIES = ("Compute", "Storage", "Database", "Networking", "DevOps", "Monitoring", "AI/ML", "Analytics", "Security/Auth")
DEFAULT_PATH = Path(__file__).with_name("pricing_reference.json")


@dataclass
class Workload:
    daily_active_users: int = 50_000
    days: int = 30
    hours: int = 730
    api_requests: int = 10_000_000
    cdn_requests: int = 2_000_000
    storage_gib: int = 2_048
    egress_gib: int = 1_024
    min_vm: int = 2
    avg_vm: int = 4
    max_vm: int = 10
    regions: int = 2
    db_replicas: int = 2
    db_disk_gib: int = 100
    vm_disk_gib: int = 64
    backup_gib: int = 200
    event_calls: int = 1_000_000
    builds_daily: int = 10
    build_mins: int = 10
    logs_gib: int = 100
    ml_hours_day: float = 4.0
    replication_gib: int = 100
    scale_api_with_users: bool = False

    def __post_init__(self):
        assert 1 <= self.days <= 31, "Days must be from 1 to 31"
        assert self.hours > 0 and self.daily_active_users > 0
        assert 2 <= self.min_vm <= self.avg_vm <= self.max_vm <= 10, "Fleet must stay within the required 2-10 VM range"
        assert self.regions >= 2 and self.db_replicas >= self.regions, "Multi-region configuration requires two regions"
        for name, v in asdict(self).items():
            if not isinstance(v, bool) and name not in ("min_vm", "max_vm", "avg_vm", "days", "hours", "regions", "db_replicas"):
                assert v >= 0, f"{name} must be nonnegative"

    @property
    def actual_api_requests(self) -> int:
        if self.scale_api_with_users:
            return round(self.api_requests * self.daily_active_users / 50_000)
        return self.api_requests

    @property
    def actual_cdn_requests(self) -> int:
        if self.scale_api_with_users:
            return round(self.cdn_requests * self.daily_active_users / 50_000)
        return self.cdn_requests


def load_default_prices(path: str | Path = DEFAULT_PATH) -> pd.DataFrame:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = pd.DataFrame(payload["rows"])
    rows["rate"] = pd.to_numeric(rows["rate"], errors="raise").astype("float64")
    rows["source"] = rows["source"].fillna("")
    return rows


def validate_prices(df: pd.DataFrame) -> pd.DataFrame:
    required = {"provider", "category", "service", "unit", "rate", "formula_key", "source", "note", "status"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required pricing fields: {sorted(missing)}")
    result = df.copy()
    result["rate"] = pd.to_numeric(result["rate"], errors="raise").astype("float64")
    if result["rate"].isna().any() or not (result["rate"] >= 0).all():
        raise ValueError("Every unit price must be a nonnegative number")
    if not set(result["provider"]).issubset(PROVIDERS):
        raise ValueError("Unknown cloud provider")
    if len(result) != len(result[["provider", "service"]].drop_duplicates()):
        raise ValueError("Duplicate provider/service pricing rows")
    return result


def usage_quantity(key: str, workload: Workload, service: str = "") -> float:
    w = workload
    key_map = {
        "vm_hours": w.avg_vm * w.hours,
        "db_hours": w.db_replicas * w.hours,
        "objects": w.storage_gib * w.regions,
        "avg_vm": w.avg_vm,
        "block": w.vm_disk_gib * w.avg_vm,
        "backup": w.backup_gib,
        "db_storage": w.db_disk_gib * w.db_replicas,
        "lbs": w.hours * w.regions,
        "egress": w.egress_gib,
        "cdn_req": w.actual_cdn_requests / 10_000,
        "api_m": w.actual_api_requests / 1_000_000,
        "replication": w.replication_gib,
        "build_minutes": w.builds_daily * w.days * w.build_mins,
        "logs": w.logs_gib,
        "ml_hours": w.ml_hours_day * w.days,
    }
    if key == "constant":
        # The price reference treats functions as a per-month bundle for
        # 1M calls, not as a live SDK SKU. Make it scale with function calls.
        if "events" in service.lower():
            return w.event_calls / 1_000_000
        return 1.0
    if key not in key_map:
        raise ValueError(f"Unknown quantity formula key: {key}")
    return float(key_map[key])


def calculate(workload: Workload, prices: pd.DataFrame) -> pd.DataFrame:
    model = validate_prices(prices)
    model["quantity"] = [usage_quantity(str(r.formula_key), workload, str(r.service)) for r in model.itertuples()]
    model["monthly_usd"] = model["quantity"] * model["rate"]
    # NOTE: no free tier, credits, tax, cloud support, PCI third-party fees,
    # cloud backup access/restore fees, or vendor-negotiated commitments.
    return model


def comparison_table(costs: pd.DataFrame) -> pd.DataFrame:
    table = costs.pivot_table(index="category", columns="provider", values="monthly_usd", aggfunc="sum", fill_value=0)
    table = table.reindex(index=CATEGORIES, columns=PROVIDERS, fill_value=0)
    table.loc["TOTAL"] = table.sum()
    return table


def totals(costs: pd.DataFrame) -> dict[str, float]:
    t = costs.groupby("provider")["monthly_usd"].sum()
    return {p: round(float(t.get(p, 0)), 2) for p in PROVIDERS}


def scenario_totals(w: Workload, rates: pd.DataFrame, vm_counts=(2, 4, 10)) -> pd.DataFrame:
    records=[]
    for count in vm_counts:
        w2 = Workload(**{**asdict(w), "avg_vm": max(w.min_vm, min(w.max_vm, count))})
        for p, amount in totals(calculate(w2, rates)).items():
            records.append({"Average active VMs": w2.avg_vm, "Cloud": p, "Monthly USD": amount})
    return pd.DataFrame(records)


def committed_costs(costs: pd.DataFrame, min_instances: int, hours: int, discount_pct: float) -> pd.DataFrame:
    """Illustrative commitment discount on guaranteed base VMs only.

    Do NOT apply reserved pricing to burst VMs or unrelated services.
    This is hypothetical scenario math; verify official plan rates.
    """
    out=costs.copy()
    discount=max(0, min(0.9, discount_pct / 100))
    out["commit_savings_usd"]=0.0
    for i, row in out.iterrows():
        if row["formula_key"] == "vm_hours":
            committed_hours=min_instances*hours
            out.at[i, "commit_savings_usd"] = min(row["monthly_usd"], committed_hours*row["rate"]*discount)
    out["committed_monthly_usd"] = out["monthly_usd"]-out["commit_savings_usd"]
    return out


OPTIMIZATIONS = {
    "AWS": [
        ("Savings Plans / Reserved Instances", "Commit the always-on 2-VM baseline, leave burst 2–10 fleet pay-as-you-go.", "Actual discounts, utilization and upfront amortization must be verified."),
        ("Right-size EC2 and RDS", "Profile CPU/memory and scale down oversized instances.", "Protect API latency, database latency, and region failover capacity."),
        ("S3 lifecycle policies", "Tier rarely used catalog assets and backups to lower-cost classes.", "Account for retrieval and minimum storage duration fees."),
        ("CloudFront caching", "Serve images and immutable React bundles through cache with compression.", "Keep personalized/API responses correct; origin and invalidation cost remain."),
        ("CloudWatch logging optimization", "Reduce duplicate DEBUG traces; retain required audit/payment logs.", "Never discard security or compliance logs."),
        ("Spot for retryable ML", "Use Spot instances for checkpointable batch training.", "Do not place primary orders/payment services on interruptible nodes."),
    ],
    "Azure": [
        ("VM reservations or Azure savings plan", "Cover the steady VM baseline, retain pay-as-you-go burst capacity.", "Review one-/three-year obligation before purchase."),
        ("VM Scale Sets tuning", "Optimize autoscale thresholds and schedules.", "Retain minimum availability across two regions."),
        ("Blob Hot/Cool lifecycle", "Move low-access objects to Cool/Cold storage.", "Consider retrieval and early-deletion charges."),
        ("Azure Monitor log tiers", "Use appropriate log plans and retention by log class.", "Preserve searchable logs needed for alerts and security."),
        ("Database right-sizing", "Review PostgreSQL and Cosmos DB capacity against production throughput.", "Avoid under-provisioning order processing."),
        ("Optimize Azure Pipelines", "Tune build minutes, caching and hosted parallel jobs.", "Still complete 10 builds per day."),
    ],
    "GCP": [
        ("Compute committed use discounts", "Apply commitments only to stable CPU/RAM baseline.", "Scope/term and actual discounts differ by SKU."),
        ("Compute Engine machine sizing", "Analyze E2 VM CPU and memory with autoscaling.", "Review performance under peak concurrency."),
        ("Cloud Storage lifecycle", "Move infrequently accessed objects to lower-cost classes.", "Check retrieval fees and retention windows."),
        ("Cloud Logging retention", "Reduce redundant debug streams, retain full required operational/security logs.", "Maintain audit coverage for payment events."),
        ("Cloud Build efficiency", "Use cacheable builds and suitable worker sizes.", "Maintain 10-builds/day requirement."),
        ("Vertex AI batch scheduling", "Run recommendation jobs in batches; choose Spot when tasks can resume.", "Avoid serving stale recommendations and uncheckpointed training."),
    ],
}


ARCHITECTURE = [
    ("Frontend / CDN", "React on S3 + CloudFront", "React on Blob / Static Web Apps + Front Door", "React on Cloud Storage + Cloud CDN"),
    ("Compute / autoscale", "EC2 Auto Scaling, 2–10 VMs", "Virtual Machine Scale Sets, 2–10 VMs", "Managed Instance Groups, 2–10 VMs"),
    ("API", "API Gateway + ALB", "API Management + Load Balancer", "API Gateway + Cloud Load Balancing"),
    ("Serverless events", "AWS Lambda", "Azure Functions", "Cloud Run functions"),
    ("User authentication", "Amazon Cognito", "Microsoft Entra External ID", "Identity Platform"),
    ("Transactions", "RDS PostgreSQL", "Azure Database for PostgreSQL", "Cloud SQL PostgreSQL"),
    ("NoSQL catalog / sessions", "DynamoDB", "Cosmos DB", "Firestore"),
    ("Files / block / backup", "S3 + EBS + snapshots", "Blob + managed disks + snapshots", "Cloud Storage + PD + snapshots"),
    ("DNS", "Route 53", "Azure DNS", "Cloud DNS"),
    ("CI/CD", "Git + CodePipeline / CodeBuild", "Git + Azure DevOps / Pipelines", "Git + Cloud Build"),
    ("Logs / metrics / alerts", "CloudWatch", "Azure Monitor", "Cloud Logging / Monitoring"),
    ("Real-time analytics", "EventBridge + Athena", "Event Hubs + analytics", "Pub/Sub + BigQuery"),
    ("ML recommendations", "SageMaker AI", "Azure Machine Learning", "Vertex AI"),
    ("Multi-region continuity", "us-east-1 + us-east-2", "East US + East US 2", "us-central1 + us-east1"),
    ("Payment processing", "External PCI-compliant provider", "External PCI-compliant provider", "External PCI-compliant provider"),
]


def architecture_dataframe() -> pd.DataFrame:
    return pd.DataFrame(ARCHITECTURE, columns=["Component", "AWS", "Azure", "GCP"])


def optimization_dataframe() -> pd.DataFrame:
    return pd.DataFrame([{"Cloud":p,"Strategy":title,"Implementation":impl,"Trade-off":caveat}
                         for p, entries in OPTIMIZATIONS.items() for title,impl,caveat in entries])


def report_html(w: Workload, costs: pd.DataFrame) -> str:
    comp=comparison_table(costs)
    total=totals(costs)
    winner=min(total, key=total.get)
    css="""<style>body{font-family:Arial,Helvetica,sans-serif;margin:40px;color:#1b2937}
    h1,h2{color:#19415c}table{border-collapse:collapse;width:100%;margin:14px 0 28px}
    td,th{border:1px solid #dae2e9;padding:8px;font-size:12px;text-align:left;vertical-align:top}
    th{background:#e8f3fa}p,li{font-size:13px;line-height:1.5}
    .note{background:#fff8e4;padding:12px;border-left:4px solid #d8a330}
    .small{font-size:11px;color:#485b6b}</style>"""
    def frame(df, money_columns=()):
        df=df.copy()
        for c in money_columns:
            df[c]=df[c].map(lambda n:f"${float(n):,.2f}")
        return df.to_html(index=False, escape=True, border=0)
    wl=pd.DataFrame([(k,v) for k,v in asdict(w).items()], columns=["Assumption","Value"])
    cats=comp.reset_index().rename(columns={"category":"Cost category"})
    pr=costs[["provider","category","service","quantity","unit","rate","monthly_usd","status","source"]].copy()
    pr["rate"]=pr["rate"].map(lambda x: f"${x:,.8f}")
    pr["monthly_usd"]=pr["monthly_usd"].map(lambda x: f"${x:,.2f}")
    rows="".join(f"<li><strong>{escape(p)}:</strong> {escape(' / '.join(row['Strategy'] for _,row in optimization_dataframe()[optimization_dataframe()['Cloud']==p].iterrows()))}</li>" for p in PROVIDERS)
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Cloud Economics Lab 7</title>{css}</head>
    <body><h1>Cloud Economics — Lab 7</h1><p>Cloud-Native E-Commerce & Analytics Platform | Generated {date.today().isoformat()} | USD/month</p>
    <div class='note'><strong>Price integrity:</strong> Planning exercise, not a vendor quotation. Some seed rates are published references, some are
    assumptions or budget allowances; verify each SKU, tier, region and free allowance with official AWS, Azure and GCP pricing calculators.
    The model does not use live APIs and excludes taxes, payment-processor fees, support plans and negotiation discounts.</div>
    <h2>1. Workload and scope</h2>{frame(wl)}
    <h2>2. Equivalent architecture</h2>{frame(architecture_dataframe())}
    <h2>3. Cost breakdown (USD/month)</h2>{frame(cats, PROVIDERS)}
    <h2>4. Detailed service calculations</h2>{frame(pr)}
    <h2>5. Cost optimization (at least five per cloud)</h2>{frame(optimization_dataframe())}
    <h2>6. Comparative analysis</h2><p>On-demand is suitable for uncertain burst capacity, while 1–3 year reservations or
    spending commitments can lower the cost of stable baseline capacity. Never assume commitment savings apply to all burst instances.
    Watch data egress, CDN/API request costs, cross-region replication, backup/restore, log ingestion and retention, database I/O,
    serverless duration, and ML serving. Cost predictability varies with demand, region, free allowances and vendor rate tiers.</p>
    <h2>7. Recommendation</h2><p><strong>Lowest modeled cost: {escape(winner)} (${total[winner]:,.2f}/month).</strong>
    This is a conditional model ranking, not an assertion that this provider is universally cheapest or offers the best value.
    Best value depends on reliability, cloud expertise, operation complexity, service performance, analytics integration,
    required compliance and confirmed vendor quotes. Verify two-region failover and performance before selection.</p>
    <h2>8. Official pricing calculators</h2><ul>
    <li><a href='https://calculator.aws/'>AWS Pricing Calculator</a></li>
    <li><a href='https://azure.microsoft.com/pricing/calculator/'>Azure Pricing Calculator</a></li>
    <li><a href='https://cloud.google.com/products/calculator'>GCP Pricing Calculator</a></li></ul>
    <p class='small'>Method: monthly quantity × USD unit rate; totals are the sum of service line items, with outbound CDN transfer charged once.
    A service with status Planning is an unverified allowance and must be replaced by calculator output for a final quote.</p></body></html>"""
