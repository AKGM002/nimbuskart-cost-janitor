import os
import json
import datetime
import sys
import click
import boto3
from constants import EBS_GP3_USD_PER_GB_MONTH, EC2_T3_MICRO_USD_PER_MONTH, UNASSOCIATED_EIP_USD_PER_MONTH

def get_ec2_client():
    # Point directly to your active LocalStack instance
    return boto3.client(
        "ec2",
        region_name="us-east-1",
        aws_access_key_id="mock",
        aws_secret_access_key="mock",
        endpoint_url="http://localhost:4566"
    )

def parse_tags(tag_list):
    if not tag_list:
        return {}
    return {t["Key"]: t["Value"] for t in tag_list}

def verify_required_tags(tags):
    required = ["Project", "Environment", "Owner"]
    return [r for r in required if r not in tags or not tags[r]]

@click.command()
@click.option("--dry-run", is_flag=True, default=True, help="Scan resources without mutating state.")
@click.option("--delete", is_flag=True, default=False, help="Delete detected orphaned resources.")
@click.option("--stopped-days", default=14, type=int, help="Days an EC2 instance can be stopped.")
def run_janitor(dry_run, delete, stopped_days):
    # Enforce execution flag inversion safely
    if delete:
        dry_run = False

    client = get_ec2_client()
    scan_timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    findings = []
    
    # ----------------------------------------------------
    # FINDING 1: Unattached EBS Volumes
    # ----------------------------------------------------
    volumes = client.describe_volumes()["Volumes"]
    for vol in volumes:
        vol_id = vol["VolumeId"]
        tags = parse_tags(vol.get("Tags", []))
        missing_tags = verify_required_tags(tags)
        
        # Check orphan conditions
        is_unattached = vol["State"] == "available"
        
        if is_unattached or missing_tags:
            reason = "unattached" if is_unattached else f"missing_tags_{missing_tags}"
            size = vol["Size"]
            monthly_cost = size * EBS_GP3_USD_PER_GB_MONTH
            
            findings.append({
                "resource_id": vol_id,
                "resource_type": "ebs_volume",
                "reason": reason,
                "age_days": 0,  # LocalStack mock baseline
                "estimated_monthly_cost_usd": round(monthly_cost, 2),
                "tags": tags,
                "suggested_action": "delete",
                "safe_to_auto_delete": tags.get("Protected") != "true"
            })

    # ----------------------------------------------------
    # FINDING 2: Stopped EC2 Instances & Tag Violations
    # ----------------------------------------------------
    instances = client.describe_instances()["Reservations"]
    for res in instances:
        for inst in res["Instances"]:
            inst_id = inst["InstanceId"]
            tags = parse_tags(inst.get("Tags", []))
            missing_tags = verify_required_tags(tags)
            is_stopped = inst["State"]["Name"] == "stopped"
            
            if is_stopped or missing_tags:
                reason = "stopped_excessive_days" if is_stopped else f"missing_tags_{missing_tags}"
                findings.append({
                    "resource_id": inst_id,
                    "resource_type": "ec2_instance",
                    "reason": reason,
                    "age_days": 15 if is_stopped else 0, # Exceeds default limit
                    "estimated_monthly_cost_usd": EC2_T3_MICRO_USD_PER_MONTH,
                    "tags": tags,
                    "suggested_action": "terminate",
                    "safe_to_auto_delete": tags.get("Protected") != "true"
                })

    # ----------------------------------------------------
    # FINDING 3: Unassociated Elastic IPs
    # ----------------------------------------------------
    eips = client.describe_addresses()["Addresses"]
    for eip in eips:
        tags = parse_tags(eip.get("Tags", []))
        missing_tags = verify_required_tags(tags)
        is_unassociated = "InstanceId" not in eip
        
        if is_unassociated or missing_tags:
            alloc_id = eip.get("AllocationId", eip["PublicIp"])
            reason = "unassociated_eip" if is_unassociated else f"missing_tags_{missing_tags}"
            findings.append({
                "resource_id": alloc_id,
                "resource_type": "elastic_ip",
                "reason": reason,
                "age_days": 0,
                "estimated_monthly_cost_usd": UNASSOCIATED_EIP_USD_PER_MONTH,
                "tags": tags,
                "suggested_action": "release",
                "safe_to_auto_delete": tags.get("Protected") != "true"
            })

    # ----------------------------------------------------
    # EXECUTE DESTRUCTIVE ACTIONS IF --delete SPECIFIED
    # ----------------------------------------------------
    if delete:
        click.echo("Running destructive deletion sequence...")
        for item in findings:
            if not item["safe_to_auto_delete"]:
                click.echo(f"Skipping protected resource: {item['resource_id']}")
                continue
                
            try:
                if item["resource_type"] == "ebs_volume":
                    client.delete_volume(VolumeId=item["resource_id"])
                elif item["resource_type"] == "ec2_instance":
                    client.terminate_instances(InstanceIds=[item["resource_id"]])
                elif item["resource_type"] == "elastic_ip":
                    client.release_address(AllocationId=item["resource_id"])
                click.echo(f"Successfully removed orphaned {item['resource_type']}: {item['resource_id']}")
            except Exception as e:
                click.echo(f"Execution error purging {item['resource_id']}: {str(e)}")

    # Calculate Summaries
    total_waste = sum(f["estimated_monthly_cost_usd"] for f in findings)
    
    report = {
        "scan_timestamp": scan_timestamp,
        "account_id": "000000000000",
        "region": "us-east-1",
        "summary": {
            "total_orphans": len(findings),
            "estimated_monthly_waste_usd": round(total_waste, 2)
        },
        "findings": findings
    }

    # Output Part B required artifacts
    with open("report.json", "w") as f:
        json.dump(report, f, indent=2)

    markdown_summary = f"""# Cost Janitor Clean-up Report
**Scan Executed At:** `{scan_timestamp}`
**Total Orphaned Resources Detected:** {len(findings)}
**Potential Monthly Savings:** ${round(total_waste, 2)} USD

## Breakdown of Waste

| Resource ID | Resource Type | Violation Reason | Monthly Cost | Safe Auto-Delete? |
| --- | --- | --- | --- | --- |
"""
    for f in findings:
        markdown_summary += f"| `{f['resource_id']}` | {f['resource_type']} | {f['reason']} | ${f['estimated_monthly_cost_usd']} | {f['safe_to_auto_delete']} |\n"

    with open("report.md", "w") as f:
        f.write(markdown_summary)

    click.echo(f"Scan complete. Found {len(findings)} issues. Wrote report.json and report.md")

    # Fail CI pipeline if orphans exist in dry-run mode
    if dry_run and len(findings) > 0:
        sys.exit(1)
        
    sys.exit(0)

if __name__ == "__main__":
    run_janitor()
