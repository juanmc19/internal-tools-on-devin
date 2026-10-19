"""Policy engine: each app declares roles, permissions, row scope, masking and approval rules in
`policy.yaml`; routes and services call `require`, `scoped`, `mask` and the approval checks.

Everything fails closed: an undeclared permission or role is refused, a role without a scope cannot
load, and a user with no role in the app gets nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import Select, false

from backend.platform import masking
from backend.platform.auth import User
from backend.platform.errors import ApiError


class PolicyError(Exception):
    """Raised at load time when policy.yaml is inconsistent."""


@dataclass(frozen=True)
class Role:
    name: str
    label: str
    permissions: frozenset[str]
    scope_field: str | None  # None means all rows
    scope_attribute: str | None  # user attribute holding the allowed values
    masking: str  # "none" or a masking profile name


@dataclass(frozen=True)
class CountRule:
    field: str
    gt: float
    count: int


@dataclass(frozen=True)
class ApprovalRule:
    step: str
    distinct_from: tuple[str, ...]
    default_count: int = 1
    count_rules: tuple[CountRule, ...] = ()


@dataclass(frozen=True)
class Policy:
    app: str
    name: str
    permissions: frozenset[str]
    roles: dict[str, Role]
    profiles: dict[str, dict[str, str]]
    approvals: dict[str, ApprovalRule] = field(default_factory=dict)

    # ---- loading -------------------------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> Policy:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Policy:
        app = raw.get("app")
        if not app:
            raise PolicyError("policy.yaml needs an 'app' key")
        permissions = frozenset(raw.get("permissions") or [])
        if not permissions:
            raise PolicyError(f"{app}: declare at least one permission")
        profiles: dict[str, dict[str, str]] = dict((raw.get("masking") or {}).get("profiles") or {})
        for pname, fields in profiles.items():
            for fname, strategy in fields.items():
                if strategy not in masking.STRATEGIES:
                    raise PolicyError(
                        f"{app}: profile '{pname}' field '{fname}' uses unknown strategy '{strategy}'"
                    )

        roles: dict[str, Role] = {}
        for rname, rdef in (raw.get("roles") or {}).items():
            rdef = rdef or {}
            perms = frozenset(rdef.get("permissions") or [])
            unknown = perms - permissions
            if unknown:
                raise PolicyError(f"{app}: role '{rname}' grants undeclared permissions {sorted(unknown)}")
            if "scope" not in rdef:
                raise PolicyError(f"{app}: role '{rname}' must declare a scope ('all' or field/attribute)")
            scope = rdef["scope"]
            if scope == "all":
                scope_field = scope_attribute = None
            elif isinstance(scope, dict) and scope.get("field") and scope.get("attribute"):
                scope_field, scope_attribute = str(scope["field"]), str(scope["attribute"])
            else:
                raise PolicyError(f"{app}: role '{rname}' has an invalid scope {scope!r}")
            mask_profile = str(rdef.get("masking", "none"))
            if mask_profile != "none" and mask_profile not in profiles:
                raise PolicyError(f"{app}: role '{rname}' uses unknown masking profile '{mask_profile}'")
            roles[rname] = Role(
                name=rname,
                label=str(rdef.get("label") or rname.replace("_", " ").capitalize()),
                permissions=perms,
                scope_field=scope_field,
                scope_attribute=scope_attribute,
                masking=mask_profile,
            )
        if not roles:
            raise PolicyError(f"{app}: declare at least one role")

        approvals: dict[str, ApprovalRule] = {}
        for step, adef in (raw.get("approvals") or {}).items():
            adef = adef or {}
            count = adef.get("count") or {}
            rules = []
            for rule in count.get("rules") or []:
                when = rule.get("when") or {}
                if "field" not in when or "gt" not in when or "then" not in rule:
                    raise PolicyError(
                        f"{app}: approval '{step}' count rule needs when.field, when.gt and then"
                    )
                rules.append(
                    CountRule(field=str(when["field"]), gt=float(when["gt"]), count=int(rule["then"]))
                )
            approvals[step] = ApprovalRule(
                step=step,
                distinct_from=tuple(str(p) for p in adef.get("distinct_from") or []),
                default_count=int(count.get("default", 1)),
                count_rules=tuple(rules),
            )

        return cls(
            app=app,
            name=str(raw.get("name") or app),
            permissions=permissions,
            roles=roles,
            profiles=profiles,
            approvals=approvals,
        )

    # ---- role lookup ---------------------------------------------------------------------------

    def role_for(self, user: User) -> Role:
        assignment = user.role_in(self.app)
        if assignment is None:
            raise ApiError(403, "NO_ROLE", f"You have no role in {self.name}.", app=self.app)
        role = self.roles.get(assignment.role)
        if role is None:
            raise ApiError(
                403, "UNKNOWN_ROLE", f"Role '{assignment.role}' is not defined for {self.name}.", app=self.app
            )
        return role

    def has(self, user: User, permission: str) -> bool:
        assignment = user.role_in(self.app)
        role = self.roles.get(assignment.role) if assignment else None
        return bool(role and permission in self.permissions and permission in role.permissions)

    # ---- the API routes use ---------------------------------------------------------------------

    def require(
        self, user: User, permission: str, *, record_type: str | None = None, record_id: str | None = None
    ) -> Role:
        if permission not in self.permissions:
            raise ApiError(
                403,
                "UNKNOWN_PERMISSION",
                f"Permission '{permission}' is not defined for {self.name}.",
                app=self.app,
            )
        role = self.role_for(user)
        if permission not in role.permissions:
            raise ApiError(
                403,
                "FORBIDDEN",
                f"{role.label}s cannot {permission.split('.', 1)[-1].replace('_', ' ')} in {self.name}.",
                app=self.app,
                record_type=record_type,
                record_id=record_id,
            )
        return role

    def scoped(self, user: User, stmt: Select, model: type) -> Select:
        """Restricts `stmt` to the rows the user's role may see. Used by lists, counts and lookups by id."""
        assignment = user.role_in(self.app)
        role = self.roles.get(assignment.role) if assignment else None
        if role is None:
            return stmt.where(false())
        if role.scope_field is None:
            return stmt
        column = getattr(model, role.scope_field, None)
        if column is None:
            raise PolicyError(f"{self.app}: scope field '{role.scope_field}' not on {model.__name__}")
        allowed = list(assignment.attributes.get(role.scope_attribute, []) or []) if assignment else []
        if not allowed:
            return stmt.where(false())
        return stmt.where(column.in_(allowed))

    def masked_fields(self, user: User) -> dict[str, str]:
        assignment = user.role_in(self.app)
        role = self.roles.get(assignment.role) if assignment else None
        if role is None:
            return {
                name: strategy for profile in self.profiles.values() for name, strategy in profile.items()
            }
        if role.masking == "none":
            return {}
        return self.profiles[role.masking]

    def is_masked(self, user: User) -> bool:
        return bool(self.masked_fields(user))

    def mask(self, user: User, record: dict[str, Any]) -> dict[str, Any]:
        fields = self.masked_fields(user)
        if not fields:
            return record
        out = dict(record)
        for name, strategy in fields.items():
            if name in out:
                out[name] = masking.apply(strategy, out[name])
        return out

    # ---- approvals / separation of duties --------------------------------------------------------

    def approval(self, step: str) -> ApprovalRule:
        rule = self.approvals.get(step)
        if rule is None:
            raise PolicyError(f"{self.app}: no approval rule declared for step '{step}'")
        return rule

    def check_separation(
        self, step: str, actor_id: str, record: Any, *, record_type: str, record_id: str
    ) -> None:
        """Refuses when the actor already acted in one of the steps the rule says they must differ from."""
        rule = self.approval(step)
        for path in rule.distinct_from:
            for earlier in _resolve(record, path):
                if earlier is not None and str(earlier) == actor_id:
                    label = path.split(".")[0].replace("_", " ")
                    raise ApiError(
                        403,
                        "SOD_VIOLATION",
                        f"Separation of duties: the person recorded as {label} cannot {step} this record.",
                        app=self.app,
                        record_type=record_type,
                        record_id=record_id,
                    )

    def required_approvals(self, step: str, record: Any) -> int:
        rule = self.approval(step)
        for count_rule in rule.count_rules:
            values = _resolve(record, count_rule.field)
            value = values[0] if values else None
            if value is not None and float(value) > count_rule.gt:
                return count_rule.count
        return rule.default_count

    def approvals_complete(self, step: str, record: Any, approver_ids: list[str]) -> bool:
        return len(set(approver_ids)) >= self.required_approvals(step, record)


def _resolve(obj: Any, path: str) -> list[Any]:
    """Resolves a dotted path on a dict or object; list values fan out ("approvals.approver_id")."""
    current: list[Any] = [obj]
    for part in path.split("."):
        nxt: list[Any] = []
        for item in current:
            if item is None:
                continue
            value = item.get(part) if isinstance(item, dict) else getattr(item, part, None)
            if isinstance(value, list | tuple | set):
                nxt.extend(value)
            else:
                nxt.append(value)
        current = nxt
    return current
