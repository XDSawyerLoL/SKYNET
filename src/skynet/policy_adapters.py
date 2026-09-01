from __future__ import annotations

from dataclasses import asdict

from .policy import Mandate


class ERC8196Adapter:
    """Projects a SKYNET mandate into ERC-8196 policy fields.

    This is a deterministic projection, not an on-chain signer or wallet.
    Ethereum execution remains an optional external adapter.
    """

    @staticmethod
    def compile(mandate: Mandate) -> dict:
        allowed_contracts = [x for x in mandate.allowed_targets if x != "*"]
        blocked_contracts = [x for x in mandate.blocked_targets if x != "*"]
        return {
            "standard": "ERC-8196",
            "policyId": mandate.mandate_id,
            "agentId": mandate.agent_id,
            "allowedActions": list(mandate.allowed_actions),
            "allowedContracts": allowed_contracts,
            "blockedContracts": blocked_contracts,
            "maxValuePerTx": mandate.max_value_per_action or 0,
            "maxValuePerDay": mandate.max_value_per_day or 0,
            "validAfter": int(mandate.valid_after),
            "validUntil": int(mandate.valid_until),
            "minVerificationScore": int(mandate.max_risk_score),
            "policyHash": mandate.policy_hash,
        }


class AP2ConstraintAdapter:
    """Projects a canonical mandate into AP2-style constraints.

    This does not create a signed AP2 VDC. A future payment provider adapter can
    wrap these constraints in the applicable AP2 mandate credential format.
    """

    @staticmethod
    def compile(mandate: Mandate) -> dict:
        return {
            "standard": "AP2-constraint-projection",
            "mandate_id": mandate.mandate_id,
            "constraints": {
                "allowed_actions": mandate.allowed_actions,
                "allowed_targets": mandate.allowed_targets,
                "blocked_targets": mandate.blocked_targets,
                "max_value_per_action": mandate.max_value_per_action,
                "max_value_per_day": mandate.max_value_per_day,
                "valid_after": mandate.valid_after,
                "valid_until": mandate.valid_until,
                "reversible_only": mandate.reversible_only,
                "max_risk_score": mandate.max_risk_score,
            },
            "canonical": asdict(mandate),
            "policy_hash": mandate.policy_hash,
        }


class OAuthScopeAdapter:
    """Maps actions to delegated authorization scopes without binding SKYNET to one OAuth provider."""

    @staticmethod
    def compile(mandate: Mandate) -> dict:
        scopes = [f"action:{action}" for action in mandate.allowed_actions if action != "*"]
        return {
            "standard": "oauth-scope-projection",
            "subject": mandate.principal,
            "agent": mandate.agent_id,
            "scopes": scopes,
            "expires_at": int(mandate.valid_until),
            "policy_hash": mandate.policy_hash,
        }
