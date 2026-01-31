"""Cloudflare API service for managing Zero Trust Access applications."""

from typing import Any

from cloudflare import Cloudflare


class CloudflareService:
    """Service for managing Cloudflare Zero Trust Access applications via API."""

    def __init__(
        self,
        account_id: str | None = None,
        api_token: str | None = None,
        api_key: str | None = None,
        api_email: str | None = None,
    ) -> None:
        """Initialize Cloudflare service.

        Supports two authentication methods:
        1. API Token (recommended): Pass api_token
        2. Global API Key (legacy): Pass api_key and api_email

        Args:
            account_id: Cloudflare account ID (optional, can be fetched)
            api_token: Cloudflare API token (for token auth)
            api_key: Cloudflare Global API key (for key auth)
            api_email: Cloudflare account email (for key auth)
        """
        if api_token:
            self.client = Cloudflare(api_token=api_token)
        elif api_key and api_email:
            self.client = Cloudflare(api_key=api_key, api_email=api_email)
        else:
            raise ValueError(
                "Must provide either api_token or both api_key and api_email"
            )
        self._account_id = account_id

    @property
    def account_id(self) -> str:
        """Get account ID, fetching from API if not set."""
        if self._account_id is None:
            self._account_id = self._fetch_account_id()
        return self._account_id

    def _fetch_account_id(self) -> str:
        """Fetch the first account ID from the API.

        Returns:
            Account ID string

        Raises:
            ValueError: If no accounts found
        """
        response = self.client.accounts.list()
        accounts = list(response)
        if not accounts:
            raise ValueError("No Cloudflare accounts found for this API key")
        # Return the first account ID
        return accounts[0].id

    def list_applications(self) -> list[dict[str, Any]]:
        """List all Access applications in the account.

        Returns:
            List of application dictionaries
        """
        response = self.client.zero_trust.access.applications.list(
            account_id=self.account_id
        )
        return response.result if hasattr(response, 'result') else []

    def get_application_by_domain(self, domain: str) -> dict[str, Any] | None:
        """Get an Access application by domain.

        Args:
            domain: Application domain (e.g., memory-dev.redleif.dev)

        Returns:
            Application dictionary or None if not found
        """
        applications = self.list_applications()
        for app in applications:
            if app.get('domain') == domain:
                return app
        return None

    def create_application(
        self,
        name: str,
        domain: str,
        session_duration: str = "24h",
        allowed_idps: list[str] | None = None,
        auto_redirect_to_identity: bool = False,
    ) -> dict[str, Any]:
        """Create a new Access application.

        Args:
            name: Application name
            domain: Application domain
            session_duration: Session duration (e.g., "24h", "1h")
            allowed_idps: List of identity provider IDs (optional)
            auto_redirect_to_identity: Skip identity provider selection page

        Returns:
            Created application dictionary

        Raises:
            Exception: If creation fails
        """
        params: dict[str, Any] = {
            "account_id": self.account_id,
            "name": name,
            "domain": domain,
            "type": "self_hosted",
            "session_duration": session_duration,
            "auto_redirect_to_identity": auto_redirect_to_identity,
        }

        if allowed_idps:
            params["allowed_idps"] = allowed_idps

        response = self.client.zero_trust.access.applications.create(**params)
        return response.result if hasattr(response, 'result') else response

    def update_application(
        self,
        application_id: str,
        name: str | None = None,
        domain: str | None = None,
        session_duration: str | None = None,
        allowed_idps: list[str] | None = None,
        auto_redirect_to_identity: bool | None = None,
    ) -> dict[str, Any]:
        """Update an existing Access application.

        Args:
            application_id: Application ID
            name: Application name (optional)
            domain: Application domain (optional)
            session_duration: Session duration (optional)
            allowed_idps: List of identity provider IDs (optional)
            auto_redirect_to_identity: Skip identity provider selection page (optional)

        Returns:
            Updated application dictionary

        Raises:
            Exception: If update fails
        """
        params: dict[str, Any] = {
            "account_id": self.account_id,
            "application_id": application_id,
        }

        if name is not None:
            params["name"] = name
        if domain is not None:
            params["domain"] = domain
        if session_duration is not None:
            params["session_duration"] = session_duration
        if allowed_idps is not None:
            params["allowed_idps"] = allowed_idps
        if auto_redirect_to_identity is not None:
            params["auto_redirect_to_identity"] = auto_redirect_to_identity

        response = self.client.zero_trust.access.applications.update(**params)
        return response.result if hasattr(response, 'result') else response

    def create_or_update_application(
        self,
        name: str,
        domain: str,
        session_duration: str = "24h",
        allowed_idps: list[str] | None = None,
        auto_redirect_to_identity: bool = False,
    ) -> dict[str, Any]:
        """Create or update an Access application.

        If an application with the domain exists, it will be updated.
        Otherwise, a new application will be created.

        Args:
            name: Application name
            domain: Application domain
            session_duration: Session duration (e.g., "24h", "1h")
            allowed_idps: List of identity provider IDs (optional)
            auto_redirect_to_identity: Skip identity provider selection page

        Returns:
            Application dictionary and whether it was created (True) or updated (False)
        """
        existing = self.get_application_by_domain(domain)
        if existing:
            app_id = existing.get("id") or existing.get("uid")
            if not app_id:
                raise ValueError(f"Application found but missing ID: {existing}")

            updated = self.update_application(
                application_id=app_id,
                name=name,
                session_duration=session_duration,
                allowed_idps=allowed_idps,
                auto_redirect_to_identity=auto_redirect_to_identity,
            )
            return {"application": updated, "created": False}
        else:
            created = self.create_application(
                name=name,
                domain=domain,
                session_duration=session_duration,
                allowed_idps=allowed_idps,
                auto_redirect_to_identity=auto_redirect_to_identity,
            )
            return {"application": created, "created": True}

    def list_policies(self, application_id: str) -> list[dict[str, Any]]:
        """List policies for an Access application.

        Args:
            application_id: Application ID

        Returns:
            List of policy dictionaries
        """
        response = self.client.zero_trust.access.applications.policies.list(
            account_id=self.account_id,
            application_id=application_id,
        )
        return response.result if hasattr(response, 'result') else []

    def create_policy(
        self,
        application_id: str,
        name: str,
        decision: str = "allow",
        include: list[dict[str, Any]] | None = None,
        exclude: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create an Access policy for an application.

        Args:
            application_id: Application ID
            name: Policy name
            decision: Policy decision ("allow" or "deny")
            include: Include rules (list of dicts with "email" or "email_domain")
            exclude: Exclude rules (optional)

        Returns:
            Created policy dictionary

        Raises:
            Exception: If creation fails
        """
        params: dict[str, Any] = {
            "account_id": self.account_id,
            "application_id": application_id,
            "name": name,
            "decision": decision,
        }

        if include:
            params["include"] = include
        if exclude:
            params["exclude"] = exclude

        response = self.client.zero_trust.access.applications.policies.create(**params)
        return response.result if hasattr(response, 'result') else response

    def ensure_policy(
        self,
        application_id: str,
        name: str,
        decision: str = "allow",
        include: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Ensure a policy exists for an application.

        If a policy with the same name exists, returns it.
        Otherwise, creates a new policy.

        Args:
            application_id: Application ID
            name: Policy name
            decision: Policy decision ("allow" or "deny")
            include: Include rules (list of dicts with "email" or "email_domain")

        Returns:
            Policy dictionary and whether it was created (True) or existed (False)
        """
        policies = self.list_policies(application_id)
        for policy in policies:
            if policy.get("name") == name:
                return {"policy": policy, "created": False}

        created = self.create_policy(
            application_id=application_id,
            name=name,
            decision=decision,
            include=include,
        )
        return {"policy": created, "created": True}
