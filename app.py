"""Cloud Economics Lab 7 — interactive three-cloud comparative cost model.

Run: streamlit run app.py

Pricing data is a user-editable EDUCATIONAL MODEL, not a live quote.
"""
from __future__ import annotations

from dataclasses import asdict
from io import BytesIO
import json
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from assignment_baseline import breakdown as assignment_breakdown, summary as assignment_summary, FACTORS, aws_detail

from cost_engine import (
    ARCHITECTURE,
    CATEGORIES,
    OPTIMIZATIONS,
    PROVIDERS,
    Workload,
    architecture_dataframe,
    calculate,
    committed_costs,
    comparison_table,
    load_default_prices,
    optimization_dataframe,
    report_html,
    scenario_totals,
    totals,
    validate_prices,
)

st.set_page_config(page_title="CloudCost Compare · Lab 7", page_icon="☁️", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """<style>
        :root { --navy:#13253b; --blue:#166a9e; --muted:#637388; }
        .block-container {padding-top:1.65rem;padding-bottom:3.5rem;max-width:1450px}
        h1,h2,h3 {letter-spacing:-0.025em;color:#183149}
        h1 {font-size:2.3rem!important;font-weight:780!important;margin:.1rem 0 .35rem}
        .eyebrow {font-size:.77rem;letter-spacing:.14em;text-transform:uppercase;font-weight:750;color:#1485a8}
        .lede {font-size:1rem;color:#53667a;line-height:1.55;margin-bottom:1.1rem}
        .muted {color:#5e7084;font-size:.87rem}
        .card {border:1px solid #dae4ee;background:#f9fbfd;padding:1.15rem 1.2rem;border-radius:13px;margin-bottom:1rem}
        .card .title {color:#52667b;font-size:.78rem;text-transform:uppercase;letter-spacing:.08em;font-weight:800}
        .card .num {font-weight:800;color:#173a57;font-size:1.95rem;letter-spacing:-.04em;margin-top:.2rem}
        .card .sub {font-size:.84rem;color:#687c8d;margin-top:.1rem}
        .tag {display:inline-block;font-size:.74rem;background:#e3f1f7;color:#185c77;border-radius:22px;padding:.26rem .65rem;margin-right:.45rem}
        .warn {border-left:3px solid #d0a54d;padding:9px 12px;background:#fff8eb;color:#64542f;font-size:.88rem}
        .stDownloadButton button {font-weight:600}
        div[data-testid='stMetric'] {border:1px solid #dce6ed;padding:.95rem 1rem;border-radius:10px;background:#fafcff}
        div[data-testid='stMetricValue'] {color:#123956}
        section[data-testid='stSidebar'] {background:#f7fafd}
        a {color:#166a9e}
    </style>""",
    unsafe_allow_html=True,
)

DEFAULT_W = Workload()
DEFAULT_KEYS = {
    "dau": DEFAULT_W.daily_active_users,
    "api": DEFAULT_W.api_requests,
    "objects": DEFAULT_W.storage_gib,
    "traffic": DEFAULT_W.egress_gib,
    "fleet": DEFAULT_W.avg_vm,
    "logvolume": DEFAULT_W.logs_gib,
    "mlhours": DEFAULT_W.ml_hours_day,
    "buildmins": DEFAULT_W.build_mins,
    "cdnhits": DEFAULT_W.cdn_requests,
    "eventcalls": DEFAULT_W.event_calls,
    "database_disk": DEFAULT_W.db_disk_gib,
    "vmdisk": DEFAULT_W.vm_disk_gib,
    "backup": DEFAULT_W.backup_gib,
    "replication": DEFAULT_W.replication_gib,
    "scale_requests": False,
}
for key, value in DEFAULT_KEYS.items():
    if key not in st.session_state:
        st.session_state[key] = value
if "prices" not in st.session_state:
    st.session_state["prices"] = load_default_prices()


@st.cache_data(show_spinner=False)
def read_architecture():
    return architecture_dataframe()


def money(value: float) -> str:
    return f"${float(value):,.2f}"


def download_csv(label: str, data: pd.DataFrame, filename: str, key: str):
    st.download_button(label, data.to_csv(index=False).encode("utf-8-sig"), filename, "text/csv", key=key)


def cloud_bar(t: dict[str, float]):
    df = pd.DataFrame([{"Cloud": x, "Monthly USD": t[x]} for x in PROVIDERS])
    fig = px.bar(df, x="Cloud", y="Monthly USD", text="Monthly USD", color="Cloud",
                 color_discrete_map={"AWS":"#eab46e", "Azure":"#5b9fe0", "GCP":"#51b4a7"})
    fig.update_traces(texttemplate="$%{text:,.2f}", textposition="outside", marker_line_width=0)
    fig.update_layout(showlegend=False, height=340, margin=dict(l=5, r=10, t=30, b=5),
                      yaxis_title="USD / month", xaxis_title="", plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)", yaxis=dict(showgrid=True, gridcolor="#e6edf3"))
    fig.update_yaxes(range=[0,max(t.values())*1.22])
    return fig


def stack_chart(costs: pd.DataFrame):
    data = costs.groupby(["provider", "category"], as_index=False)["monthly_usd"].sum()
    fig = px.bar(data, x="provider", y="monthly_usd", color="category",
                 category_orders={"provider":list(PROVIDERS), "category":list(CATEGORIES)},
                 labels={"provider":"Cloud", "monthly_usd":"USD / month", "category":"Cost area"})
    fig.update_layout(height=410, margin=dict(l=5,r=5,t=24,b=0), legend=dict(orientation="h", y=-.22),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    return fig


def show_rate_warning():
    st.info("**Pricing integrity:** This is an editable educational budget model, not a live AWS/Azure/GCP quotation. "
            "'Planning' and 'Calculated' rows are assumptions; even published reference rates must be matched to exact SKU, tier, location and date. "
            "Verify with official pricing calculators before submission. Free tiers, taxes, payment processor charges and support plans are excluded.")


def default_difference(w: Workload) -> list[str]:
    important = ["daily_active_users", "api_requests", "storage_gib", "egress_gib", "builds_daily", "min_vm", "max_vm"]
    dw=asdict(DEFAULT_W); cw=asdict(w)
    return [k for k in important if cw[k] != dw[k]]


with st.sidebar:
    st.markdown("<div class='eyebrow'>Cloud Economics</div>", unsafe_allow_html=True)
    st.markdown("### LAB 07 / WORKSPACE")
    page = st.radio("Navigation", ["Lab 7 final comparison", "Executive dashboard", "Architecture", "Pricing & evidence",
                                  "Optimization", "Comparative analysis", "Export & submission"],
                    label_visibility="collapsed")
    st.divider()
    st.markdown("#### Workload configuration")
    st.caption("Mandatory lab baseline is pre-loaded. Changes are for what-if analysis.")
    st.number_input("Daily active users", min_value=1000, max_value=5_000_000, step=5000, key="dau")
    st.number_input("API requests / month", min_value=0, max_value=1_000_000_000, step=1_000_000, key="api")
    st.number_input("Object storage (GiB)", min_value=1, max_value=1_000_000, step=256, key="objects")
    st.number_input("Outbound traffic (GiB/month)", min_value=0, max_value=1_000_000, step=256, key="traffic")
    st.slider("Average active VMs (min 2, max 10)", min_value=2, max_value=10, key="fleet")
    with st.expander("Advanced modeling assumptions"):
        st.number_input("CDN requests/month", min_value=0, max_value=1_000_000_000, step=100_000, key="cdnhits")
        st.number_input("Function events/month", min_value=0, max_value=100_000_000, step=100_000, key="eventcalls")
        st.number_input("Log ingestion (GiB/month)", min_value=0, max_value=100_000, step=10, key="logvolume")
        st.slider("ML batch runtime (hours/day)", min_value=0.0, max_value=24.0, step=0.5, key="mlhours")
        st.number_input("Average build duration (minutes)", min_value=1, max_value=240, step=5, key="buildmins")
        st.number_input("DB storage per replica (GiB)", min_value=10, max_value=4096, step=10, key="database_disk")
        st.number_input("VM disk per VM (GiB)", min_value=16, max_value=4096, step=16, key="vmdisk")
        st.number_input("Backup storage (GiB)", min_value=0, max_value=100_000, step=50, key="backup")
        st.number_input("Cross-region replication data (GiB)", min_value=0, max_value=100_000, step=50, key="replication")
        st.checkbox("Scale requests with DAU", key="scale_requests",
                    help="Optional scenario: scale API/CDN requests proportionally from the mandated 50,000 DAU baseline.")
    if st.button("Reset workload to Lab baseline", use_container_width=True):
        for key, val in DEFAULT_KEYS.items():
            st.session_state[key] = val
        st.rerun()
    st.divider()
    st.caption("2-region architecture · 730 compute hours/month · 30-day CI/CD month · USD excluding taxes")

w = Workload(
    daily_active_users=int(st.session_state.dau), api_requests=int(st.session_state.api),
    storage_gib=int(st.session_state.objects), egress_gib=int(st.session_state.traffic),
    avg_vm=int(st.session_state.fleet), logs_gib=int(st.session_state.logvolume),
    ml_hours_day=float(st.session_state.mlhours), build_mins=int(st.session_state.buildmins),
    cdn_requests=int(st.session_state.cdnhits), event_calls=int(st.session_state.eventcalls),
    db_disk_gib=int(st.session_state.database_disk), vm_disk_gib=int(st.session_state.vmdisk),
    backup_gib=int(st.session_state.backup), replication_gib=int(st.session_state.replication),
    scale_api_with_users=bool(st.session_state.scale_requests),
)
prices = validate_prices(st.session_state.prices)
costs = calculate(w, prices)
scenario_cloud_totals = totals(costs)
final_summary = assignment_summary()
final_breakdown = assignment_breakdown()
cloud_totals = dict(zip(final_summary['Cloud'], final_summary['Monthly USD']))
winner = min(cloud_totals, key=cloud_totals.get)

st.markdown("<div class='eyebrow'>Hands-on FinOps · interactive comparative model</div>", unsafe_allow_html=True)
st.title("CloudCost Compare")
st.markdown("<p class='lede'>AWS  /  Microsoft Azure  /  Google Cloud — Cloud-native e-commerce and analytics platform.<br/>"
            "Change usage, inspect service-level prices, and evaluate architecture and optimization trade-offs.</p>",
            unsafe_allow_html=True)
st.markdown("<span class='tag'>50k baseline daily users</span><span class='tag'>2 regions</span>"
            "<span class='tag'>2–10 auto-scaling VMs</span><span class='tag'>10M API requests/month</span>", unsafe_allow_html=True)

changed=default_difference(w)
if changed:
    st.warning("**What-if scenario:** You changed assignment-mandatory workload inputs: " + ", ".join(changed) + ". "
               "Use **Reset workload to Lab baseline** before capturing final assignment evidence.")

if page == "Lab 7 final comparison":
    st.subheader("Lab 7 · Final three-cloud cost comparison")
    st.info("**Evidence:** AWS is taken from the supplied official AWS Pricing Calculator CSV. "
            "Azure and GCP are hypothetical category-adjusted estimates derived from AWS, "
            "not exports or quotes from their official calculators. This is a frozen assignment scenario; "
            "sidebar what-if controls apply to the other model pages, not this comparison.")
    final = assignment_summary()
    detail = assignment_breakdown()
    cols = st.columns(3)
    for idx, cloud in enumerate(PROVIDERS):
        row = final[final.Cloud == cloud].iloc[0]
        with cols[idx]:
            st.metric(cloud, money(row['Monthly USD']))
            st.caption(f"{money(row['Annual USD'])} / year · {row['Evidence']}")
    st.plotly_chart(cloud_bar(dict(zip(final.Cloud, final['Monthly USD']))), use_container_width=True)
    st.markdown("#### Seven required cost categories · USD/month")
    display = detail.copy()
    for provider in PROVIDERS:
        display[provider] = display[provider].map(money)
    st.dataframe(display, hide_index=True, use_container_width=True)
    st.caption("AWS line items sum to $1,352.05 before the calculator's $0.01 summary rounding adjustment; "
               "the authoritative AWS estimate total is $1,352.06.")
    st.markdown("#### Calculation method and assumptions")
    st.latex(r"\text{Peer category cost} = \text{AWS category cost} \times \text{scenario factor}")
    factors = pd.DataFrame([{'Category': c, 'Azure factor': f['Azure'], 'GCP factor': f['GCP']} for c,f in FACTORS.items()])
    st.dataframe(factors, hide_index=True, use_container_width=True)
    st.caption("Factors are assumptions for a classroom comparison, not measured vendor-to-vendor price ratios. "
               "Both peer estimates inherit AWS's specific service coverage and omissions. "
               "The AWS export includes two regions, but some services appear only in Virginia; "
               "the baseline is not a validated equivalent production architecture.")
    st.markdown("#### Conditional conclusion")
    st.success("Under the stated factor assumptions, **GCP is the lowest modeled cost**, "
               "followed by AWS and Azure. This is not evidence that GCP would actually be cheapest "
               "for an independently configured, production-equivalent deployment.")
    st.markdown("**Trade-offs:** AWS provides an established service ecosystem and an auditable calculator baseline. "
                "Azure may fit Microsoft-centered environments. GCP offers analytics and ML integration. "
                "Verify database HA, CDN traffic, online ML inference, logs, support, and cross-region replication before procurement.")
    st.markdown("#### Download assignment evidence")
    a, b, c = st.columns(3)
    with a:
        download_csv("Download cost summary", final, "Lab7_final_summary.csv", "final_summary")
    with b:
        download_csv("Download category breakdown", detail, "Lab7_final_breakdown.csv", "final_breakdown")
    with c:
        download_csv("Download AWS line items", aws_detail(), "Lab7_AWS_official_line_items.csv", "final_aws")
    st.markdown("For scenario exploration, use **Executive dashboard**. Its independent editable rate catalog "
                "is not calibrated to the frozen AWS-based assignment comparison above.")

elif page == "Executive dashboard":
    st.subheader("Monthly cost · Lab 7 submitted baseline")
    st.caption("Consistent with the Final Comparison page. AWS is calculator-derived; Azure/GCP are factor-based estimates. Sidebar inputs do not alter these submitted figures.")
    cols = st.columns(3)
    for idx, cloud in enumerate(PROVIDERS):
        with cols[idx]:
            st.metric(cloud, money(cloud_totals[cloud]), "Lowest estimated" if cloud == winner else None, delta_color="off")
            st.caption(f"{money(cloud_totals[cloud]*12)} per year")
    a, b = st.columns([1,1.1], gap="large")
    with a:
        st.markdown("#### Three-cloud comparison")
        st.plotly_chart(cloud_bar(cloud_totals), use_container_width=True)
    with b:
        st.markdown("#### Cost composition")
        long = final_breakdown.melt(id_vars='Category', var_name='Cloud', value_name='USD/month')
        fig = px.bar(long, x='Cloud', y='USD/month', color='Category', category_orders={'Cloud':list(PROVIDERS)})
        st.plotly_chart(fig, use_container_width=True)
    st.markdown("#### Seven required cost categories · USD/month")
    formatted = final_breakdown.copy()
    for provider in PROVIDERS:
        formatted[provider] = formatted[provider].map(money)
    st.dataframe(formatted, hide_index=True, use_container_width=True)
    st.info("Optional interactive what-if estimates are available under **Pricing & evidence**. They use a separate editable price catalog and must not be mixed with the submitted Lab 7 totals.")

elif page == "Architecture":
    st.subheader("Equivalent e-commerce architectures")
    st.write("All options serve React, Node.js/Python APIs, accounts, products, payment integration, orders, "
             "analytics, recommendations, monitoring and CI/CD. Two regions provide continuity; database replication is a modeled assumption.")
    st.dataframe(read_architecture(), use_container_width=True, hide_index=True)
    cloud=st.selectbox("Select architecture flow", list(PROVIDERS), index=0)
    labels={
        "AWS": ["React • S3 + CloudFront", "Route 53", "API Gateway + ALB", "EC2 Auto Scaling", "RDS PostgreSQL", "DynamoDB", "Lambda events", "SageMaker AI", "CloudWatch"],
        "Azure": ["React • Blob + Front Door", "Azure DNS", "API Mgmt + Load Balancer", "VM Scale Sets", "Azure PostgreSQL", "Cosmos DB", "Azure Functions", "Azure ML", "Azure Monitor"],
        "GCP": ["React • Storage + Cloud CDN", "Cloud DNS", "API Gateway + Cloud LB", "Managed Instance Groups", "Cloud SQL", "Firestore", "Cloud Run functions", "Vertex AI", "Cloud Monitoring"],
    }
    a=labels[cloud]
    dot = f'''digraph cloud {{
      graph [rankdir=LR, bgcolor="transparent", nodesep=0.48, ranksep=0.72, pad="0.3"];
      node [shape=box, style="rounded,filled", fillcolor="#eaf4fa", color="#8cb4ca", fontname="Arial", fontsize=11, margin="0.12,0.1"];
      edge [color="#648ba6", arrowsize=0.65];
      client [label="50k daily users", fillcolor="#dbf4e9"];
      dns [label="{a[1]}"]; front [label="{a[0]}"];
      gate [label="{a[2]}"]; vm [label="{a[3]}\\n2–10 instances"];
      sql [label="{a[4]}"]; nosql [label="{a[5]}"];
      fn [label="{a[6]}"]; ai [label="{a[7]}"]; monitor [label="{a[8]}"];
      client -> dns -> front -> gate -> vm; vm -> sql; vm -> nosql; vm -> fn -> ai;
      vm -> monitor [style=dashed]; fn -> monitor [style=dashed];
    }}'''
    st.graphviz_chart(dot, use_container_width=True)
    st.caption("Conceptual architecture flow; production design must include private networking, WAF, secrets management, "
               "PCI-compliant payment integration, multi-region failover and identity/IAM controls. "
               "Do not interpret the flow as an automatically deployed infrastructure stack.")
    st.markdown("#### Scope and cost modeling")
    st.markdown("- **Compute:** Linux VMs with comparable 2 vCPU / 8 GiB specs and always-on baseline. "
                "Serverless handles background events.\n"
                "- **Storage:** 2,048 GiB logical objects × 2 regions plus block disks and backups.\n"
                "- **Database:** production-style relational replicas plus NoSQL estimated operations/storage.\n"
                "- **Network:** CDN transfer, API requests, load balancing, DNS and cross-region replication.\n"
                "- **Operations:** 10 builds/day, full logging, alerts, analytics and batch ML.\n"
                "- **Financial exclusions:** third-party payment transaction fees, enterprise support, taxes, licenses, VPN and unexpected incident spending.")

elif page == "Pricing & evidence":
    st.subheader("Editable unit price catalog")
    st.write("Prices are provided as **starting estimates**, not a realtime API. Change rates to the values shown in the "
             "official calculators, and record the verification status plus URL in each row.")
    show_rate_warning()
    st.markdown("**Official calculators:** [AWS](https://calculator.aws/) · "
                "[Azure](https://azure.microsoft.com/pricing/calculator/) · "
                "[Google Cloud](https://cloud.google.com/products/calculator)")
    rate_status=prices.groupby(["provider","status"]).size().unstack(fill_value=0)
    with st.expander("Current evidence status", expanded=False):
        st.dataframe(rate_status, use_container_width=True)
    cloud_filter=st.selectbox("Provider to edit", ["AWS", "Azure", "GCP"], index=0)
    working=prices.loc[prices.provider==cloud_filter].copy().reset_index(drop=True)
    shown=["category","service","unit","rate","status","source","note"]
    editor=st.data_editor(
        working[shown], hide_index=True, use_container_width=True, num_rows="fixed",
        column_config={
            "category":st.column_config.TextColumn("Cost area", disabled=True),
            "service":st.column_config.TextColumn("Service", disabled=True, width="large"),
            "unit":st.column_config.TextColumn("Rate unit", disabled=True),
            "rate":st.column_config.NumberColumn("USD per unit", min_value=0.0, step=0.00000001, format="%.8f",
                                                   help="Eight-decimal input, for tiny function request rates."),
            "status":st.column_config.SelectboxColumn("Price status", options=["Planning", "Published", "Corroborated", "Calculated", "User-entered", "Calculator-verified"]),
            "source":st.column_config.LinkColumn("Public price/source URL", display_text="Open source"),
            "note":st.column_config.TextColumn("Assumption / evidence notes", width="large"),
        },
        disabled=["category", "service", "unit"], key=f"price_editor_{cloud_filter}",
    )
    a,b,c=st.columns([1,1,2])
    with a:
        apply = st.button("Apply edited rates", type="primary", use_container_width=True)
    with b:
        if st.button("Restore original prices", use_container_width=True):
            st.session_state["prices"]=load_default_prices()
            for cloud in PROVIDERS:
                st.session_state.pop(f"price_editor_{cloud}",None)
            st.rerun()
    if apply:
        updated=prices.copy()
        for rec in editor.to_dict(orient="records"):
            match=(updated.provider==cloud_filter)&(updated.service==rec["service"])
            old_rate=float(updated.loc[match,"rate"].iloc[0])
            rate=float(rec["rate"])
            status=str(rec["status"])
            if abs(old_rate-rate)>1e-12 and status in ("Planning", "Published", "Corroborated", "Calculated"):
                status="User-entered"
            for name,val in {"rate":rate,"source":rec["source"],"note":rec["note"],"status":status}.items():
                updated.loc[match,name]=val
        try:
            st.session_state["prices"]=validate_prices(updated)
            st.success("Pricing changes applied. Dashboard and exported reports will use these updated rates.")
            st.rerun()
        except Exception as exc:
            st.error(f"Cannot save price changes: {exc}")
    st.divider()
    download_csv("Download current pricing catalog (CSV)", prices, "lab7_price_catalog.csv", "dl_prices")
    incoming=st.file_uploader("Import updated pricing CSV (same columns as catalog)", type=["csv"],
                             help="Rate column uses floating point; source and status must be supplied. No network request is made.")
    if incoming is not None and st.button("Validate & load imported prices"):
        try:
            uploaded=pd.read_csv(incoming)
            cleaned=validate_prices(uploaded)
            assert set(zip(cleaned.provider,cleaned.service))==set(zip(prices.provider,prices.service)), "Imported catalog must preserve all service rows"
            st.session_state["prices"]=cleaned
            for cloud in PROVIDERS:
                st.session_state.pop(f"price_editor_{cloud}",None)
            st.success("Imported prices loaded.")
            st.rerun()
        except Exception as exc:
            st.error(f"Import failed: {exc}")
    st.markdown("#### Service-by-service what-if calculations (NOT submitted Lab 7 totals)")
    details=calculate(w, st.session_state.prices)
    st.dataframe(details[["provider", "category", "service", "quantity", "unit", "rate", "monthly_usd", "status"]],
                 use_container_width=True, hide_index=True,
                 column_config={"rate":st.column_config.NumberColumn("USD / unit",format="%.8f"),
                                "monthly_usd":st.column_config.NumberColumn("USD / month",format="$%.2f"),
                                "quantity":st.column_config.NumberColumn("Units",format="%.2f")})

elif page == "Optimization":
    st.subheader("Optimization recommendations · at least 5 per cloud")
    st.caption("The baseline amounts across this app are the frozen Lab 7 comparison. The discount example below is a separate what-if model.")
    st.write("Recommendations are tied to resource demand and operating risks, rather than guaranteed savings claims.")
    optim=optimization_dataframe()
    for cloud in PROVIDERS:
        with st.expander(f"{cloud} · {len(OPTIMIZATIONS[cloud])} strategies", expanded=(cloud==winner)):
            st.dataframe(optim[optim.Cloud==cloud][["Strategy","Implementation","Trade-off"]],
                         use_container_width=True, hide_index=True)
    st.divider()
    st.markdown("#### Optional what-if: base capacity commitment scenario (not the submitted baseline)")
    st.write("Only the guaranteed **2 always-on VMs** are eligible for a hypothetical discount. "
             "The remaining average capacity stays on-demand. These discounts are editable modeling assumptions, not vendor quotes.")
    discount=st.slider("Illustrative reserved / savings discount on baseline VMs",0,65,30,5)
    projected=committed_costs(costs,w.min_vm,w.hours,discount)
    summary=[]
    for cloud in PROVIDERS:
        rows=projected[projected.provider==cloud]
        summary.append({"Cloud":cloud,"On-demand modeled USD":rows.monthly_usd.sum(),
                        "Hypothetical committed USD":rows.committed_monthly_usd.sum(),
                        "Modeled savings USD":rows.commit_savings_usd.sum()})
    st.warning("The following on-demand and discounted figures are generated by the separate editable rate catalog; they are NOT the Lab 7 comparison totals shown on the dashboard.")
    st.dataframe(pd.DataFrame(summary), hide_index=True, use_container_width=True,
                 column_config={col:st.column_config.NumberColumn(format="$%.2f") for col in
                                ["On-demand modeled USD","Hypothetical committed USD","Modeled savings USD"]})
    st.caption("Note: Savings Plans, Azure reservations, and GCP committed use discounts have different scopes and terms. "
               "Do not apply one assumed percentage to an actual purchase without official pricing verification.")
    st.markdown("#### Hidden cost watchlist")
    st.markdown("**Data egress and CDN** · **API Gateway/request tiers** · **inter-region replication** · "
                "**database read/write operations** · **storage retrieval and backup restoration** · "
                "**full-log ingestion/retention** · **ML endpoint uptime** · **payment processing and support charges**.")

elif page == "Comparative analysis":
    st.subheader("Pricing, management and cost predictability")
    st.caption("Cost ranking below uses the same frozen submitted figures as the Final Comparison and Executive Dashboard pages.")
    compare=pd.DataFrame([
        {"Dimension":"On-demand / pay-as-you-go", "AWS":"EC2 On-Demand; Lambda", "Azure":"VM Pay-As-You-Go; Functions", "GCP":"Compute Engine on-demand; Cloud Run functions"},
        {"Dimension":"Long-term discounted options", "AWS":"Reserved Instances / Savings Plans", "Azure":"Reservations / Azure Savings Plan", "GCP":"Committed use discounts"},
        {"Dimension":"Interruptible workloads", "AWS":"EC2 Spot", "Azure":"Spot Virtual Machines", "GCP":"Spot VMs"},
        {"Dimension":"Cost management", "AWS":"Cost Explorer, Budgets, Cost & Usage Report", "Azure":"Cost Management, Budgets, Advisor", "GCP":"Cloud Billing, Budgets, FinOps Hub"},
        {"Dimension":"Hidden cost exposure", "AWS":"Data egress, CloudFront, API, CloudWatch", "Azure":"Front Door, API Management, Log Analytics", "GCP":"Cloud CDN, API, Logging, replication"},
        {"Dimension":"Cost predictability", "AWS":"High for reserved baseline; variable event/egress", "Azure":"High for reserved baseline; monitor logs and tiers", "GCP":"High for committed baseline; variable requests/egress"},
    ])
    st.dataframe(compare, use_container_width=True, hide_index=True)
    st.markdown("#### Cost ranking · submitted Lab 7 assumptions")
    ranking=sorted(cloud_totals.items(), key=lambda item:item[1])
    for i,(cloud,usd) in enumerate(ranking,1):
        st.markdown(f"**{i}. {cloud}** — {money(usd)} per month")
    st.markdown("#### Final recommendation · submitted Lab 7 assumptions")
    st.success(f"**Lowest modeled monthly cost: {winner} ({money(cloud_totals[winner])}).** "
               "For a cost-first team, it is the provisional value choice only if the services meet performance, "
               "resilience and compliance needs and calculator-verified prices keep the same ranking.")
    st.write("**Best value is conditional.** AWS offers a broad operational ecosystem, Azure fits Microsoft-centric organizations, "
             "and GCP can be attractive for data analytics and ML. These non-price advantages have not been converted into unsupported numeric scores.")
    st.write("**Main trade-offs:** commitments may reduce steady-state costs but reduce flexibility; active-active or failover regions "
             "improve continuity but cost more; managed databases reduce operations effort but may carry premiums; "
             "aggressive log reduction lowers spending but can compromise diagnostics and audit requirements.")
    st.markdown("#### Optional sensitivity analysis · independent planning model")
    st.write("This separate editable price catalog does not reproduce the frozen submitted baseline. Test sensitivity to "
             "average compute fleet size without changing the required 2–10 VM boundaries.")
    scen=scenario_totals(w,prices,(2,4,6,8,10))
    st.plotly_chart(px.line(scen, x="Average active VMs", y="Monthly USD", color="Cloud",markers=True),
                    use_container_width=True)

elif page == "Export & submission":
    st.subheader("Submission package builder")
    st.write("Download the **submitted Lab 7 figures** first. The optional what-if outputs are provided separately and are not interchangeable with the baseline.")
    st.markdown("#### Submitted Lab 7 comparison · consistent with homepage")
    f1,f2,f3=st.columns(3)
    with f1:
        download_csv("Download FINAL cloud totals",final_summary,"Lab7_FINAL_cloud_totals.csv","export_final_totals")
    with f2:
        download_csv("Download FINAL category costs",final_breakdown,"Lab7_FINAL_category_costs.csv","export_final_categories")
    with f3:
        download_csv("Download AWS calculator line items",aws_detail(),"Lab7_AWS_calculator_line_items.csv","export_final_aws")
    st.markdown("#### Optional what-if exports · separate editable rate catalog")
    show_rate_warning()
    cols=st.columns(3)
    with cols[0]:
        download_csv("Download line-item costs",costs,"Lab7_cost_breakdown.csv","export_details")
    with cols[1]:
        download_csv("Download cloud comparison",comparison_table(costs).reset_index(),"Lab7_three_cloud_comparison.csv","export_summary")
    with cols[2]:
        download_csv("Download optimized strategies",optimization_dataframe(),"Lab7_optimizations.csv","export_optim")
    html_doc=report_html(w,costs)
    st.download_button("Download full English lab report (HTML)",html_doc,"Lab7_Cost_Comparative_Report.html",
                       "text/html",use_container_width=True)
    st.warning("The HTML report below is a separate what-if planning report, not the submitted AWS-based Lab 7 comparison. Use the FINAL CSV exports above for the submitted figures.")
    st.markdown("#### Official price verification checklist")
    verification=[
        "Open all three official pricing calculators and choose the documented regions and SKU sizes.",
        "Match the 2-region deployment and 2–10 autoscaling fleet (average 4 VMs).",
        "Use 2,048 GiB logical objects; document whether second-region replication is billed separately.",
        "Check 10M API requests, 1,024 GiB egress, CDN request rates, and serverless compute duration.",
        "Check production PostgreSQL, NoSQL operation throughput, database storage and backups.",
        "Check 10 builds/day, full-log ingestion/retention, monitoring and ML runtime.",
        "Enter calculator-confirmed prices into the catalog and mark them Calculator-verified; save reference URLs.",
        "Export the report and capture dashboard, architecture, catalog evidence, optimization and recommendation screenshots.",
    ]
    for item in verification:
        st.checkbox(item, value=False)
    st.caption("The app does not log into providers, run live pricing APIs or export vendor-generated calculator estimates; "
               "attach any screenshots/CSV provided by the real vendor calculators separately.")
    st.markdown("#### Assignment requirement coverage")
    coverage=pd.DataFrame([
        ("Mandatory workload","Sidebar and exported report","Modeled"),
        ("Three equivalent architectures","Architecture page","Covered"),
        ("Monthly cost/service and totals","Final Comparison; Executive Dashboard; FINAL CSV","AWS verified; peers hypothetical"),
        ("Seven required cost categories","Final Comparison; Executive Dashboard","Seven categories; frozen baseline"),
        ("≥5 strategies per cloud","Optimization page","Covered"),
        ("Pricing, hidden costs, management","Comparative analysis","Covered"),
        ("Cheapest, value, trade-offs","Comparative analysis; Final Comparison","Conditional GCP recommendation"),
        ("Official provider calculators","Links, evidence flags and checklist","Manual validation required"),
    ],columns=["Lab item","Where to see it","Status"])
    st.dataframe(coverage, hide_index=True, use_container_width=True)

st.divider()
st.caption(f"CloudCost Compare · Cloud Economics Lab 7 · {date.today().isoformat()} · Educational modeled costs in USD/month. "
           "Actual bills and official calculator estimates will vary by region, service SKU, free tier and usage.")
