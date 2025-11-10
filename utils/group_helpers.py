"""
Helper functions for group management
"""

from flask import session as flask_session
from sqlalchemy.orm import Session, joinedload
from models import Group, GroupMembership, User
from sqlalchemy import select
import secrets


def get_current_group_id():
    """Get the current active group ID from session"""
    return flask_session.get('current_group_id')


def set_current_group_id(group_id):
    """Set the current active group ID in session"""
    flask_session['current_group_id'] = group_id


def get_current_group(user, db_session: Session):
    """
    Get user's current active group from session.
    Falls back to first group if not set or invalid.
    """
    group_id = get_current_group_id()

    if group_id:
        # Verify user is member of this group
        group = db_session.execute(
            select(Group)
            .where(Group.id == group_id)
            .options(joinedload(Group.members))
        ).unique().scalar_one_or_none()

        if group and is_member(user.id, group_id, db_session):
            return group

    # Fallback to user's first group (usually CLAAMP)
    # Query through the session instead of accessing user.groups (which may be detached)
    membership = db_session.execute(
        select(GroupMembership)
        .where(GroupMembership.user_id == user.id)
        .options(joinedload(GroupMembership.group).joinedload(Group.members))
        .limit(1)
    ).unique().scalar_one_or_none()

    if membership:
        group = membership.group
        set_current_group_id(group.id)  # Update session
        return group

    return None


def switch_group(user_id: int, group_id: int, db_session: Session) -> bool:
    """
    Switch user's active group.
    Returns True if successful, False if user is not a member.
    """
    if is_member(user_id, group_id, db_session):
        set_current_group_id(group_id)
        return True
    return False


def is_member(user_id: int, group_id: int, db_session: Session) -> bool:
    """Check if user is a member of a group"""
    membership = db_session.execute(
        select(GroupMembership)
        .where(
            GroupMembership.user_id == user_id,
            GroupMembership.group_id == group_id
        )
    ).scalar_one_or_none()
    return membership is not None


def is_owner(user_id: int, group_id: int, db_session: Session) -> bool:
    """Check if user is the owner of a group"""
    membership = db_session.execute(
        select(GroupMembership)
        .where(
            GroupMembership.user_id == user_id,
            GroupMembership.group_id == group_id
        )
    ).scalar_one_or_none()
    return membership and membership.role == "owner"


def generate_invite_code() -> str:
    """Generate a unique invite code for private groups"""
    # Format: tfp-XXXXXXXX (8 random characters)
    return f"tfp-{secrets.token_urlsafe(8)}"


def add_user_to_group(user_id: int, group_id: int, db_session: Session, role: str = "member"):
    """Add a user to a group"""
    # Check if already a member
    if is_member(user_id, group_id, db_session):
        return False

    membership = GroupMembership(
        user_id=user_id,
        group_id=group_id,
        role=role
    )
    db_session.add(membership)
    db_session.flush()
    return True


def get_user_groups(user_id: int, db_session: Session):
    """Get all groups a user is a member of"""
    memberships = db_session.execute(
        select(GroupMembership)
        .where(GroupMembership.user_id == user_id)
        .options(joinedload(GroupMembership.group).joinedload(Group.members))
    ).unique().scalars().all()

    return [membership.group for membership in memberships]


def get_group_by_invite_code(invite_code: str, db_session: Session):
    """Find a group by its invite code"""
    return db_session.execute(
        select(Group)
        .where(Group.invite_code == invite_code)
        .options(joinedload(Group.members))
    ).unique().scalar_one_or_none()


def search_public_groups(query: str, db_session: Session):
    """Search for public groups by name"""
    return db_session.execute(
        select(Group)
        .where(Group.is_public == True)
        .where(Group.name.ilike(f"%{query}%"))
        .options(joinedload(Group.members))
        .order_by(Group.name)
    ).unique().scalars().all()
