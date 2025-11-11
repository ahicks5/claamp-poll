# groups/routes.py
from __future__ import annotations

from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from db import SessionLocal
from models import Group, GroupMembership, User, Poll, SpreadPoll
from utils.group_helpers import (
    get_current_group, get_user_groups, switch_group as switch_group_helper,
    is_member, is_owner, generate_invite_code,
    add_user_to_group, get_group_by_invite_code, search_public_groups
)

from . import bp


def require_admin():
    """Ensure current user is admin"""
    if not (current_user.is_authenticated and getattr(current_user, "is_admin", False)):
        abort(403)


@bp.get("/")
@login_required
def groups_dashboard():
    """Show all user's groups"""
    session = SessionLocal()
    try:
        user_groups = get_user_groups(current_user.id, session)
        current_group = get_current_group(current_user, session)

        return render_template(
            "groups_dashboard.html",
            user_groups=user_groups,
            current_group=current_group
        )
    finally:
        session.close()


@bp.get("/<int:group_id>")
@login_required
def group_detail(group_id: int):
    """Show group details"""
    session = SessionLocal()
    try:
        group = session.execute(
            select(Group)
            .where(Group.id == group_id)
            .options(joinedload(Group.members).joinedload(GroupMembership.user))
        ).unique().scalar_one_or_none()

        if not group:
            flash("Group not found.", "danger")
            return redirect(url_for("groups.groups_dashboard"))

        # Check if user is member (unless public group)
        user_is_member = is_member(current_user.id, group_id, session)
        user_is_owner = is_owner(current_user.id, group_id, session)

        if not group.is_public and not user_is_member:
            flash("You don't have access to this private group.", "danger")
            return redirect(url_for("groups.groups_dashboard"))

        # Get member count
        member_count = len(group.members)

        # Get some stats
        polls_count = session.execute(
            select(func.count(Poll.id)).where(Poll.group_id == group_id)
        ).scalar()

        spreads_count = session.execute(
            select(func.count(SpreadPoll.id)).where(SpreadPoll.group_id == group_id)
        ).scalar()

        return render_template(
            "group_detail.html",
            group=group,
            user_is_member=user_is_member,
            user_is_owner=user_is_owner,
            member_count=member_count,
            polls_count=polls_count,
            spreads_count=spreads_count
        )
    finally:
        session.close()


@bp.get("/search")
@login_required
def search():
    """Search public groups"""
    query = request.args.get("q", "")
    session = SessionLocal()
    try:
        if query:
            groups = search_public_groups(query, session)
        else:
            # Show all public groups
            groups = session.execute(
                select(Group)
                .where(Group.is_public == True)
                .options(joinedload(Group.members))
                .order_by(Group.name)
            ).unique().scalars().all()

        # Mark which groups user is already in
        user_groups = get_user_groups(current_user.id, session)
        user_group_ids = {g.id for g in user_groups}

        return render_template(
            "groups_search.html",
            groups=groups,
            query=query,
            user_group_ids=user_group_ids
        )
    finally:
        session.close()


@bp.post("/switch/<int:group_id>")
@login_required
def switch(group_id: int):
    """Switch active group"""
    session = SessionLocal()
    try:
        if switch_group_helper(current_user.id, group_id, session):
            flash("Switched to new group!", "success")
        else:
            flash("You are not a member of that group.", "danger")

        # Redirect back to referrer or dashboard
        return redirect(request.referrer or url_for("root"))
    finally:
        session.close()


@bp.post("/join/<int:group_id>")
@login_required
def join(group_id: int):
    """Join a public group"""
    session = SessionLocal()
    try:
        group = session.execute(
            select(Group)
            .where(Group.id == group_id)
            .options(joinedload(Group.members))
        ).unique().scalar_one_or_none()

        if not group:
            flash("Group not found.", "danger")
            return redirect(url_for("groups.search"))

        if not group.is_public:
            flash("Cannot join private group without invite.", "danger")
            return redirect(url_for("groups.search"))

        if add_user_to_group(current_user.id, group_id, session):
            session.commit()
            flash(f"Welcome to {group.name}!", "success")
            # Switch to new group
            switch_group_helper(current_user.id, group_id, session)
            return redirect(url_for("groups.group_detail", group_id=group_id))
        else:
            flash("You are already a member of this group.", "info")
            return redirect(url_for("groups.group_detail", group_id=group_id))
    finally:
        session.close()


@bp.get("/invite/<invite_code>")
def join_by_invite(invite_code: str):
    """Join group via invite link (public page, redirects to login if needed)"""
    session = SessionLocal()
    try:
        group = get_group_by_invite_code(invite_code, session)

        if not group:
            flash("Invalid invite code.", "danger")
            return redirect(url_for("auth.login"))

        # Check if user is already a member (if authenticated)
        user_is_member = is_member(current_user.id, group.id, session) if current_user.is_authenticated else False

        # Show group preview
        return render_template(
            "groups_join_preview.html",
            group=group,
            invite_code=invite_code,
            user_is_member=user_is_member
        )
    finally:
        session.close()


@bp.get("/create")
@login_required
def create_form():
    """Create new group form (admin only)"""
    require_admin()
    return render_template("groups_create.html")


@bp.post("/create")
@login_required
def create_submit():
    """Create new group (admin only)"""
    require_admin()
    session = SessionLocal()
    try:
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        is_public = request.form.get("is_public") == "on"

        # Validation
        if not name:
            flash("Group name is required.", "danger")
            return redirect(url_for("groups.create_form"))

        if len(name) < 3:
            flash("Group name must be at least 3 characters.", "danger")
            return redirect(url_for("groups.create_form"))

        # Create group
        group = Group(
            name=name,
            description=description or None,
            is_public=is_public,
            invite_code=None if is_public else generate_invite_code(),
            created_by_user_id=current_user.id
        )
        session.add(group)
        session.flush()

        # Add creator as owner
        add_user_to_group(current_user.id, group.id, session, role="owner")

        session.commit()

        flash(f"Created group: {name}", "success")
        return redirect(url_for("groups.group_detail", group_id=group.id))
    finally:
        session.close()
