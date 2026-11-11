"""Frozen Lab 7 comparison. AWS from calculator export; peers are hypothetical adjustments."""
from pathlib import Path
import pandas as pd

AWS_TOTAL = 1352.06
FACTORS = {
    'Compute': {'Azure': 1.12, 'GCP': .84},
    'Storage': {'Azure': .92, 'GCP': .86},
    'Database': {'Azure': 1.08, 'GCP': 1.03},
    'Networking': {'Azure': 1.03, 'GCP': .96},
    'DevOps': {'Azure': 1.00, 'GCP': .85},
    'Monitoring': {'Azure': 1.05, 'GCP': .90},
    'AI/ML': {'Azure': 1.25, 'GCP': 1.18},
}

CATEGORY = {
    'Amazon EC2': 'Compute', 'AWS Lambda': 'Compute',
    'S3 Standard': 'Storage',
    'Amazon RDS for PostgreSQL': 'Database', 'DynamoDB on-demand capacity': 'Database',
    'Data Transfer': 'Networking', 'AWS Data Transfer': 'Networking',
    'Amazon CloudFront': 'Networking', 'Amazon API Gateway': 'Networking',
    'Application Load Balancer': 'Networking', 'Amazon Route 53': 'Networking',
    'AWS CodeBuild': 'DevOps', 'AWS CodePipeline': 'DevOps',
    'Amazon CloudWatch': 'Monitoring',
    'SageMaker Studio Notebooks': 'AI/ML', 'SageMaker On-Demand Notebook Instances': 'AI/ML',
}

def aws_detail(path=None):
    path = Path(path) if path else Path(__file__).with_name('Lab7-AWS-CloudCost-Comparisonte.csv')
    data = pd.read_csv(path, skiprows=7, encoding='utf-8-sig')
    data = data[data['Service'].notna() & data['Monthly'].notna()].copy()
    data['Service'] = data['Service'].astype(str).str.strip()
    unknown = set(data.Service) - set(CATEGORY)
    if unknown:
        raise ValueError(f'Unmapped AWS services: {sorted(unknown)}')
    data['Category'] = data.Service.map(CATEGORY)
    return data

def breakdown():
    aws = aws_detail().groupby('Category')['Monthly'].sum().reindex(FACTORS, fill_value=0)
    result = pd.DataFrame({'Category': list(FACTORS), 'AWS': aws.values})
    for provider in ('Azure', 'GCP'):
        result[provider] = [float(aws[cat]) * FACTORS[cat][provider] for cat in FACTORS]
    # Official AWS estimate rounds independently of its raw line items.
    return result

def summary():
    detail = breakdown()
    totals = detail[['AWS','Azure','GCP']].sum()
    return pd.DataFrame({
        'Cloud': ['AWS', 'Azure', 'GCP'],
        'Monthly USD': [AWS_TOTAL, round(float(totals.Azure),2), round(float(totals.GCP),2)],
        'Evidence': ['AWS official calculator CSV', 'AWS category-factor scenario', 'AWS category-factor scenario'],
    }).assign(**{'Annual USD': lambda d: (d['Monthly USD'] * 12).round(2)})
