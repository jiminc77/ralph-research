"""Deterministic model-alias resolution."""
from __future__ import annotations


class ResolverError(Exception):
    def __init__(self, unresolved: list[str], roles: list[str]) -> None:
        self.unresolved = unresolved
        self.roles = roles
        super().__init__(
            f"unresolved aliases: {', '.join(unresolved)}; "
            f"blocking roles: {', '.join(roles)}"
        )


class ModelResolver:
    def __init__(self, alias_map: dict, catalog) -> None:
        self.alias_map = alias_map
        self.catalog = catalog

    @staticmethod
    def _alias(value):
        return value.get("alias") if isinstance(value, dict) else value

    def resolve_all(self) -> dict:
        resolved = {}
        missing = []
        roles = []
        for role, value in self.alias_map.items():
            alias = self._alias(value)
            aliases = [alias]
            if role != "reviewer" and isinstance(value, dict):
                aliases.extend(value.get("fallback_chain", []))
            model_id = None
            for candidate in aliases:
                if candidate:
                    model_id = self.catalog.resolve(candidate)
                    if model_id:
                        break
            if not model_id:
                missing.append(alias or "<missing>")
                roles.append(role)
            else:
                resolved[role] = {"alias": alias, "model_id": model_id}
        if missing:
            raise ResolverError(missing, roles)
        return resolved
