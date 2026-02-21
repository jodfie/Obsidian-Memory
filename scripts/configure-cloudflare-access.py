#!/usr/bin/env python3
"""Configure Cloudflare Access applications using Cloudflare Global API."""

import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.services.cloudflare_service import CloudflareService


def get_env_or_prompt(key: str, prompt: str, required: bool = True) -> str:
    """Get value from environment or prompt user.

    Args:
        key: Environment variable key
        prompt: Prompt message
        required: Whether value is required

    Returns:
        Value from environment or user input
    """
    value = os.environ.get(key)
    if value:
        return value

    if required:
        value = input(f"{prompt}: ").strip()
        if not value:
            print(f"❌ Error: {prompt} is required")
            sys.exit(1)
        return value
    return ""


def configure_application(
    service: CloudflareService,
    name: str,
    domain: str,
    email_domain: str | None = None,
) -> dict:
    """Configure a Cloudflare Access application.

    Args:
        service: CloudflareService instance
        name: Application name
        domain: Application domain
        email_domain: Email domain for access policy (e.g., @example.com)

    Returns:
        Configuration result dictionary
    """
    print(f"\n📝 Configuring application: {name} ({domain})")

    # Create or update application
    result = service.create_or_update_application(
        name=name,
        domain=domain,
        session_duration="24h",
        auto_redirect_to_identity=False,
    )

    app = result["application"]
    app_id = app.get("id") or app.get("uid")
    created = result["created"]

    if created:
        print(f"✅ Created application: {app_id}")
    else:
        print(f"✅ Updated existing application: {app_id}")

    # Create access policy if email domain provided
    if email_domain:
        policy_name = f"Allow {email_domain} users"
        include_rules = [{"email_domain": email_domain}]

        policy_result = service.ensure_policy(
            application_id=app_id,
            name=policy_name,
            decision="allow",
            include=include_rules,
        )

        if policy_result["created"]:
            print(f"✅ Created access policy: {policy_name}")
        else:
            print(f"ℹ️  Access policy already exists: {policy_name}")

    return {
        "application_id": app_id,
        "created": created,
        "domain": domain,
    }


def main() -> None:
    """Main configuration function."""
    print("==========================================")
    print("Cloudflare Access Configuration")
    print("Using Cloudflare Global API")
    print("==========================================")
    print()

    # Get Cloudflare API credentials - support both token and global API key
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN")
    api_key = os.environ.get("CLOUDFLARE_API_KEY")
    api_email = os.environ.get("CLOUDFLARE_EMAIL")
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")

    # Determine authentication method
    if not api_token and not (api_key and api_email):
        print("No credentials found in environment.")
        print("Choose authentication method:")
        print("  1. API Token (recommended)")
        print("  2. Global API Key + Email (legacy)")
        choice = input("Enter choice [1/2]: ").strip()

        if choice == "2":
            api_key = input("Enter Cloudflare Global API Key: ").strip()
            api_email = input("Enter Cloudflare Email: ").strip()
        else:
            api_token = input("Enter Cloudflare API Token: ").strip()

    # Initialize service
    try:
        if api_token:
            print("Using API Token authentication")
            service = CloudflareService(
                api_token=api_token,
                account_id=account_id,
            )
        else:
            print("Using Global API Key authentication")
            service = CloudflareService(
                api_key=api_key,
                api_email=api_email,
                account_id=account_id,
            )

        # Fetch account ID if not provided
        fetched_account_id = service.account_id
        print(f"✅ Cloudflare API connection successful")
        print(f"   Account ID: {fetched_account_id}")
    except Exception as e:
        print(f"❌ Error connecting to Cloudflare API: {e}")
        sys.exit(1)

    # Get team domain
    team_domain = get_env_or_prompt(
        "CLOUDFLARE_ACCESS_TEAM_DOMAIN",
        "Enter Cloudflare Access team domain (e.g., your-team.cloudflareaccess.com)",
    )

    # Get email domain for policies
    email_domain = get_env_or_prompt(
        "CLOUDFLARE_ACCESS_EMAIL_DOMAIN",
        "Enter email domain for access policy (e.g., @example.com, or leave empty to skip)",
        required=False,
    )
    if email_domain and not email_domain.startswith("@"):
        email_domain = f"@{email_domain}"

    # Configure applications
    print("\n" + "=" * 50)
    print("Configuring Access Applications")
    print("=" * 50)

    # Dev environment
    dev_domain = get_env_or_prompt(
        "CLOUDFLARE_ACCESS_DEV_DOMAIN",
        "Enter dev domain (e.g., memory-dev.example.com)",
    )
    dev_result = configure_application(
        service=service,
        name="Obsidian-Memory Dev",
        domain=dev_domain,
        email_domain=email_domain,
    )

    # Prod environment
    prod_domain = get_env_or_prompt(
        "CLOUDFLARE_ACCESS_PROD_DOMAIN",
        "Enter prod domain (e.g., memory.example.com, or leave empty to skip)",
        required=False,
    )
    prod_result = None
    if prod_domain:
        prod_result = configure_application(
            service=service,
            name="Obsidian-Memory Prod",
            domain=prod_domain,
            email_domain=email_domain,
        )

    # Summary
    print("\n" + "=" * 50)
    print("Configuration Summary")
    print("=" * 50)
    print(f"\n✅ Dev application configured: {dev_domain}")
    if prod_result:
        print(f"✅ Prod application configured: {prod_domain}")
    print(f"\nTeam domain: {team_domain}")
    if email_domain:
        print(f"Access policy: Allow {email_domain} users")

    print("\n" + "=" * 50)
    print("✅ Cloudflare Access configuration complete!")
    print("=" * 50)
    print("\nNext steps:")
    print("1. Store credentials in Infisical (see configure-cloudflare-access.sh)")
    print("2. Deploy: make dev (or make prod)")
    print("3. Test authentication flow")


if __name__ == "__main__":
    main()
