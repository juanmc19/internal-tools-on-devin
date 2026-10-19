"""Mock sign-in. `X-Dev-User` names a seeded persona and is honoured only when APP_ENV=dev, and then only for
requests from this machine (loopback peer, Host header allowlisted in `create_app`).

Production would use Entra ID OIDC; the rest of the foundation only sees `User`.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import ForeignKey, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from backend.platform.db import Base, get_session
from backend.platform.errors import ApiError


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120))
    roles: Mapped[list[UserRoleRow]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class UserRoleRow(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    app: Mapped[str] = mapped_column(String(32), primary_key=True)
    role: Mapped[str] = mapped_column(String(64))
    attributes: Mapped[dict] = mapped_column(default=dict)


@dataclass(frozen=True)
class RoleAssignment:
    app: str
    role: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class User:
    id: str
    name: str
    roles: dict[str, RoleAssignment]

    def role_in(self, app: str) -> RoleAssignment | None:
        return self.roles.get(app)


def _to_user(row: UserRow) -> User:
    return User(
        id=row.id,
        name=row.display_name,
        roles={
            r.app: RoleAssignment(app=r.app, role=r.role, attributes=dict(r.attributes or {}))
            for r in row.roles
        },
    )


def _is_loopback(host: str | None) -> bool:
    try:
        return host is not None and ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def require_dev_mode(request: Request) -> None:
    if not request.app.state.settings.dev_mode:
        raise ApiError(401, "AUTH_REQUIRED", "Mock sign-in is only available when APP_ENV=dev.")
    # if the API is bound to a non-loopback interface, other machines still cannot use the mock sign-in
    if not _is_loopback(request.client.host if request.client else None):
        raise ApiError(401, "DEV_SIGNIN_LOCAL_ONLY", "Mock sign-in only answers requests from this machine.")


def current_user(
    request: Request,
    session: Session = Depends(get_session),
    x_dev_user: str | None = Header(default=None, alias="X-Dev-User"),
) -> User:
    require_dev_mode(request)
    if not x_dev_user:
        raise ApiError(401, "AUTH_REQUIRED", "Sign in to continue (X-Dev-User header missing).")
    row = session.get(UserRow, x_dev_user)
    if row is None:
        raise ApiError(401, "UNKNOWN_USER", "Unknown user.")
    user = _to_user(row)
    request.state.user = user
    return user


def upsert_user(session: Session, *, id: str, name: str, roles: list[RoleAssignment]) -> None:
    row = session.get(UserRow, id)
    if row is None:
        row = UserRow(id=id, display_name=name)
        session.add(row)
    row.display_name = name
    existing = {r.app: r for r in row.roles}
    for assignment in roles:
        role_row = existing.get(assignment.app)
        if role_row is None:
            row.roles.append(
                UserRoleRow(app=assignment.app, role=assignment.role, attributes=assignment.attributes)
            )
        else:
            role_row.role = assignment.role
            role_row.attributes = assignment.attributes


router = APIRouter(tags=["auth"])


def _describe(request: Request, user: User) -> dict[str, Any]:
    registry = request.app.state.registry
    roles = []
    for assignment in user.roles.values():
        manifest = registry.get(assignment.app)
        policy = manifest.policy if manifest else None
        role = policy.roles.get(assignment.role) if policy else None
        scope_values: list[str] = []
        if role and role.scope_attribute:
            scope_values = [str(v) for v in assignment.attributes.get(role.scope_attribute, [])]
        roles.append(
            {
                "app": assignment.app,
                "app_name": manifest.name if manifest else assignment.app,
                "role": assignment.role,
                "role_label": role.label if role else assignment.role,
                "permissions": sorted(role.permissions) if role else [],
                "masked": role.masking != "none" if role else True,
                "scope": scope_values if role and role.scope_attribute else ["All"],
            }
        )
    return {"id": user.id, "name": user.name, "roles": roles}


@router.get("/me")
def me(request: Request, user: User = Depends(current_user)) -> dict[str, Any]:
    return _describe(request, user)


@router.get("/dev/users")
def dev_users(request: Request, session: Session = Depends(get_session)) -> dict[str, Any]:
    require_dev_mode(request)
    rows = session.scalars(select(UserRow).order_by(UserRow.id)).all()
    return {"items": [_describe(request, _to_user(row)) for row in rows]}
