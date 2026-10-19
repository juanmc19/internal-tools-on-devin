"""Policy engine: each app declares roles, permissions, row scope, masking and approval rules in
`policy.yaml`; routes and services call `require`, `scoped`, `mask` and the approval checks.

Everything fails closed: an undeclared permission or role is refused, a role without a scope cannot
load, a user with no role in the app gets nothing, and an approval rule naming a field the record does not
have is refused at registration (`check_fields`) and again at request time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import Select, false, inspect
from sqlalchemy.exc import NoInspectionAvailable

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
                if not when.get("field") or "gt" not in when or "then" not in rule:
                    raise PolicyError(
                        f"{app}: approval '{step}' count rule needs when.field, when.gt and then"
                    )
                rules.append(
                    CountRule(field=str(when["field"]), gt=float(when["gt"]), count=int(rule["then"]))
                )
            distinct_from = tuple(str(p) for p in adef.get("distinct_from") or [])
            if any(not p for p in distinct_from):
                raise PolicyError(f"{app}: approval '{step}' has an empty distinct_from path")
            default_count = int(count.get("default", 1))
            if default_count < 1 or any(r.count < 1 for r in rules):
                raise PolicyError(f"{app}: approval '{step}' counts must be at least 1")
            approvals[step] = ApprovalRule(
                step=step,
                distinct_from=distinct_from,
                default_count=default_count,
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

    def check_fields(self, model: type) -> None:
        """Fails closed at registration: every distinct_from and count-rule path must exist on `model`
        (following relationships for dotted paths), so a typo cannot silently turn a control off."""
        for rule in self.approvals.values():
            for path in rule.distinct_from:
                _check_path(self.app, rule.step, model, path)
            for count_rule in rule.count_rules:
                _check_path(self.app, rule.step, model, count_rule.field)

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
            for earlier in self._resolve(step, record, path):
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
        """The strictest count among the default and every matching rule, whatever their order."""
        rule = self.approval(step)
        required = rule.default_count
        for count_rule in rule.count_rules:
            values = [v for v in self._resolve(step, record, count_rule.field) if v is not None]
            if any(float(v) > count_rule.gt for v in values):
                required = max(required, count_rule.count)
        return required

    def approvals_complete(self, step: str, record: Any, approver_ids: list[str]) -> bool:
        return len(set(approver_ids)) >= self.required_approvals(step, record)

    def _resolve(self, step: str, obj: Any, path: str) -> list[Any]:
        try:
            return _resolve(obj, path)
        except KeyError as exc:
            raise PolicyError(
                f"{self.app}: approval '{step}' path '{path}' has no field {exc.args[0]!r} on the record"
            ) from None


def _check_path(app: str, step: str, model: type, path: str) -> None:
    """Every part of `path` but the last must be a relationship on the mapped model, the last a column."""
    current = model
    *hops, leaf = path.split(".")
    try:
        for part in hops:
            current = inspect(current).relationships[part].mapper.class_
        if leaf in inspect(current).column_attrs:
            return
    except (KeyError, NoInspectionAvailable):
        pass
    raise PolicyError(f"{app}: approval '{step}' path '{path}' is not a field on {model.__name__}")


def _resolve(obj: Any, path: str) -> list[Any]:
    """Resolves a dotted path on a dict or object; list values fan out ("approvals.approver_id").
    A missing field raises KeyError instead of reading as None, so the caller can fail closed."""
    current: list[Any] = [obj]
    for part in path.split("."):
        nxt: list[Any] = []
        for item in current:
            if item is None:
                continue
            if isinstance(item, dict):
                if part not in item:
                    raise KeyError(part)
                value = item[part]
            elif hasattr(item, part):
                value = getattr(item, part)
            else:
                raise KeyError(part)
            if isinstance(value, list | tuple | set):
                nxt.extend(value)
            else:
                nxt.append(value)
        current = nxt
    return current
