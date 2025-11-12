"""
Comprehensive admin dashboard for managing users, groups, polls, and ballots.
"""

from flask import render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from sqlalchemy import select, func, or_
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone

from db import SessionLocal
from models import User, Group, GroupMembership, Poll, Ballot, BallotItem, SpreadPoll, SpreadGame, Team
from utils.group_helpers import add_user_to_group, is_member

from . import bp


def require_admin():
    """Ensure user is an admin"""
    if not (current_user.is_authenticated and getattr(current_user, "is_admin", False)):
        abort(403)


@bp.get("/")
@login_required
def dashboard():
    """Main admin dashboard with overview stats"""
    require_admin()

    with SessionLocal() as s:
        # Get counts
        user_count = s.execute(select(func.count(User.id))).scalar_one()
        group_count = s.execute(select(func.count(Group.id))).scalar_one()
        poll_count = s.execute(select(func.count(Poll.id))).scalar_one()
        spread_poll_count = s.execute(select(func.count(SpreadPoll.id))).scalar_one()
        ballot_count = s.execute(select(func.count(Ballot.id)).where(Ballot.submitted_at.isnot(None))).scalar_one()

        # Recent activity
        recent_users = s.execute(
            select(User).order_by(User.created_at.desc()).limit(5)
        ).scalars().all()

        recent_polls = s.execute(
            select(Poll)
            .options(joinedload(Poll.group))
            .order_by(Poll.created_at.desc())
            .limit(5)
        ).unique().scalars().all()

    return render_template(
        "admin/dashboard.html",
        user_count=user_count,
        group_count=group_count,
        poll_count=poll_count,
        spread_poll_count=spread_poll_count,
        ballot_count=ballot_count,
        recent_users=recent_users,
        recent_polls=recent_polls
    )


@bp.get("/users")
@login_required
def users():
    """User management page"""
    require_admin()

    search_query = request.args.get("q", "").strip()

    with SessionLocal() as s:
        query = select(User).options(joinedload(User.group_memberships))

        if search_query:
            query = query.where(
                or_(
                    User.username.ilike(f"%{search_query}%"),
                    User.email.ilike(f"%{search_query}%")
                )
            )

        users = s.execute(
            query.order_by(User.username.asc())
        ).unique().scalars().all()

        # Get all groups for dropdown
        all_groups = s.execute(
            select(Group).order_by(Group.name.asc())
        ).scalars().all()

        # Build user data with group info
        user_data = []
        for user in users:
            memberships = s.execute(
                select(GroupMembership)
                .options(joinedload(GroupMembership.group))
                .where(GroupMembership.user_id == user.id)
            ).unique().scalars().all()

            user_data.append({
                "user": user,
                "groups": [m.group for m in memberships],
                "roles": {m.group_id: m.role for m in memberships}
            })

    return render_template(
        "admin/users.html",
        user_data=user_data,
        all_groups=all_groups,
        search_query=search_query
    )


@bp.post("/users/<int:user_id>/add-to-group")
@login_required
def add_user_to_group_post(user_id: int):
    """Add a user to a group"""
    require_admin()

    group_id = request.form.get("group_id", type=int)
    role = request.form.get("role", "member")

    if not group_id:
        flash("Group ID required.", "danger")
        return redirect(url_for("admin.users"))

    with SessionLocal() as s:
        user = s.get(User, user_id)
        group = s.get(Group, group_id)

        if not user or not group:
            flash("User or group not found.", "danger")
            return redirect(url_for("admin.users"))

        # Check if already a member
        if is_member(user_id, group_id, s):
            flash(f"{user.username} is already in {group.name}.", "warning")
        else:
            membership = GroupMembership(
                user_id=user_id,
                group_id=group_id,
                role=role
            )
            s.add(membership)
            s.commit()
            flash(f"Added {user.username} to {group.name} as {role}.", "success")

    return redirect(url_for("admin.users"))


@bp.post("/users/<int:user_id>/remove-from-group/<int:group_id>")
@login_required
def remove_user_from_group(user_id: int, group_id: int):
    """Remove a user from a group"""
    require_admin()

    with SessionLocal() as s:
        user = s.get(User, user_id)
        group = s.get(Group, group_id)

        if not user or not group:
            flash("User or group not found.", "danger")
            return redirect(url_for("admin.users"))

        membership = s.execute(
            select(GroupMembership).where(
                GroupMembership.user_id == user_id,
                GroupMembership.group_id == group_id
            )
        ).scalar_one_or_none()

        if membership:
            s.delete(membership)
            s.commit()
            flash(f"Removed {user.username} from {group.name}.", "success")
        else:
            flash(f"{user.username} is not in {group.name}.", "warning")

    return redirect(url_for("admin.users"))


@bp.post("/users/<int:user_id>/change-role/<int:group_id>")
@login_required
def change_user_role(user_id: int, group_id: int):
    """Change a user's role in a group"""
    require_admin()

    new_role = request.form.get("role", "member")

    with SessionLocal() as s:
        membership = s.execute(
            select(GroupMembership).where(
                GroupMembership.user_id == user_id,
                GroupMembership.group_id == group_id
            )
        ).scalar_one_or_none()

        if membership:
            membership.role = new_role
            s.commit()
            flash(f"Updated role to {new_role}.", "success")
        else:
            flash("Membership not found.", "danger")

    return redirect(url_for("admin.users"))


@bp.post("/users/<int:user_id>/toggle-admin")
@login_required
def toggle_admin(user_id: int):
    """Toggle admin status for a user"""
    require_admin()

    with SessionLocal() as s:
        user = s.get(User, user_id)

        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("admin.users"))

        if user.id == current_user.id:
            flash("You cannot change your own admin status.", "danger")
            return redirect(url_for("admin.users"))

        user.is_admin = not user.is_admin
        s.commit()

        status = "an admin" if user.is_admin else "a regular user"
        flash(f"{user.username} is now {status}.", "success")

    return redirect(url_for("admin.users"))


@bp.get("/groups")
@login_required
def groups():
    """Group management page"""
    require_admin()

    with SessionLocal() as s:
        all_groups = s.execute(
            select(Group)
            .options(joinedload(Group.members))
            .order_by(Group.name.asc())
        ).unique().scalars().all()

        # Build group data with member counts
        group_data = []
        for group in all_groups:
            member_count = s.execute(
                select(func.count(GroupMembership.id)).where(
                    GroupMembership.group_id == group.id
                )
            ).scalar_one()

            poll_count = s.execute(
                select(func.count(Poll.id)).where(Poll.group_id == group.id)
            ).scalar_one()

            spread_count = s.execute(
                select(func.count(SpreadPoll.id)).where(SpreadPoll.group_id == group.id)
            ).scalar_one()

            group_data.append({
                "group": group,
                "member_count": member_count,
                "poll_count": poll_count,
                "spread_count": spread_count
            })

    return render_template("admin/groups.html", group_data=group_data)


@bp.get("/groups/<int:group_id>")
@login_required
def group_detail(group_id: int):
    """Detailed group management page"""
    require_admin()

    with SessionLocal() as s:
        group = s.execute(
            select(Group)
            .options(joinedload(Group.members))
            .where(Group.id == group_id)
        ).unique().scalar_one_or_none()

        if not group:
            flash("Group not found.", "danger")
            return redirect(url_for("admin.groups"))

        # Get all members with details
        memberships = s.execute(
            select(GroupMembership)
            .join(GroupMembership.user)
            .options(joinedload(GroupMembership.user))
            .where(GroupMembership.group_id == group_id)
            .order_by(GroupMembership.role.desc(), User.username.asc())
        ).unique().scalars().all()

        # Get all users not in this group
        all_user_ids = s.execute(select(User.id)).scalars().all()
        member_user_ids = [m.user_id for m in memberships]
        non_member_ids = set(all_user_ids) - set(member_user_ids)

        non_members = []
        if non_member_ids:
            non_members = s.execute(
                select(User)
                .where(User.id.in_(non_member_ids))
                .order_by(User.username.asc())
            ).scalars().all()

        # Get polls for this group
        polls = s.execute(
            select(Poll)
            .where(Poll.group_id == group_id)
            .order_by(Poll.season.desc(), Poll.week.desc())
        ).scalars().all()

        # Get spread polls for this group
        spread_polls = s.execute(
            select(SpreadPoll)
            .where(SpreadPoll.group_id == group_id)
            .order_by(SpreadPoll.season.desc(), SpreadPoll.week.desc())
        ).scalars().all()

    return render_template(
        "admin/group_detail.html",
        group=group,
        memberships=memberships,
        non_members=non_members,
        polls=polls,
        spread_polls=spread_polls
    )


@bp.post("/groups/<int:group_id>/delete")
@login_required
def delete_group(group_id: int):
    """Delete a group"""
    require_admin()

    with SessionLocal() as s:
        group = s.get(Group, group_id)

        if not group:
            flash("Group not found.", "danger")
            return redirect(url_for("admin.groups"))

        if group.name == "CLAAMP":
            flash("Cannot delete the CLAAMP group.", "danger")
            return redirect(url_for("admin.groups"))

        group_name = group.name
        s.delete(group)
        s.commit()
        flash(f"Deleted group: {group_name}", "success")

    return redirect(url_for("admin.groups"))


@bp.post("/groups/<int:group_id>/toggle-privacy")
@login_required
def toggle_group_privacy(group_id: int):
    """Toggle a group between public and private"""
    require_admin()

    with SessionLocal() as s:
        group = s.get(Group, group_id)

        if not group:
            flash("Group not found.", "danger")
            return redirect(url_for("admin.groups"))

        # Toggle the privacy setting
        was_public = group.is_public
        group.is_public = not group.is_public

        # If switching to private, ensure we have an invite code
        if not group.is_public and not group.invite_code:
            from utils.group_helpers import generate_invite_code
            group.invite_code = generate_invite_code()

        s.commit()

        # Flash appropriate message
        if was_public:
            flash(f"'{group.name}' is now PRIVATE. Invite code: {group.invite_code}", "success")
        else:
            flash(f"'{group.name}' is now PUBLIC and searchable by anyone.", "success")

    return redirect(url_for("admin.group_detail", group_id=group_id))


@bp.get("/polls")
@login_required
def polls():
    """Poll management page"""
    require_admin()

    group_filter = request.args.get("group_id", type=int)

    with SessionLocal() as s:
        query = select(Poll).options(joinedload(Poll.group))

        if group_filter:
            query = query.where(Poll.group_id == group_filter)

        all_polls = s.execute(
            query.order_by(Poll.season.desc(), Poll.week.desc())
        ).unique().scalars().all()

        # Get ballot counts for each poll
        poll_data = []
        for poll in all_polls:
            ballot_count = s.execute(
                select(func.count(Ballot.id)).where(
                    Ballot.poll_id == poll.id,
                    Ballot.submitted_at.isnot(None)
                )
            ).scalar_one()

            poll_data.append({
                "poll": poll,
                "ballot_count": ballot_count
            })

        # Get all groups for filter dropdown
        all_groups = s.execute(
            select(Group).order_by(Group.name.asc())
        ).scalars().all()

    return render_template(
        "admin/polls.html",
        poll_data=poll_data,
        all_groups=all_groups,
        group_filter=group_filter
    )


@bp.post("/polls/<int:poll_id>/delete")
@login_required
def delete_poll(poll_id: int):
    """Delete a poll and all its ballots"""
    require_admin()

    with SessionLocal() as s:
        poll = s.get(Poll, poll_id)

        if not poll:
            flash("Poll not found.", "danger")
            return redirect(url_for("admin.polls"))

        poll_title = poll.title
        s.delete(poll)
        s.commit()
        flash(f"Deleted poll: {poll_title}", "success")

    return redirect(url_for("admin.polls"))


@bp.get("/ballots")
@login_required
def ballots():
    """Ballot management page"""
    require_admin()

    poll_filter = request.args.get("poll_id", type=int)
    user_filter = request.args.get("user_id", type=int)

    with SessionLocal() as s:
        query = (
            select(Ballot)
            .options(joinedload(Ballot.user), joinedload(Ballot.poll).joinedload(Poll.group))
            .where(Ballot.submitted_at.isnot(None))
        )

        if poll_filter:
            query = query.where(Ballot.poll_id == poll_filter)

        if user_filter:
            query = query.where(Ballot.user_id == user_filter)

        all_ballots = s.execute(
            query.order_by(Ballot.submitted_at.desc())
        ).unique().scalars().all()

        # Get all polls and users for filters
        all_polls = s.execute(
            select(Poll)
            .options(joinedload(Poll.group))
            .order_by(Poll.season.desc(), Poll.week.desc())
        ).unique().scalars().all()

        all_users = s.execute(
            select(User).order_by(User.username.asc())
        ).scalars().all()

    return render_template(
        "admin/ballots.html",
        ballots=all_ballots,
        all_polls=all_polls,
        all_users=all_users,
        poll_filter=poll_filter,
        user_filter=user_filter
    )


@bp.post("/ballots/<int:ballot_id>/delete")
@login_required
def delete_ballot(ballot_id: int):
    """Delete a specific ballot"""
    require_admin()

    with SessionLocal() as s:
        ballot = s.execute(
            select(Ballot)
            .options(joinedload(Ballot.user))
            .where(Ballot.id == ballot_id)
        ).unique().scalar_one_or_none()

        if not ballot:
            flash("Ballot not found.", "danger")
            return redirect(url_for("admin.ballots"))

        user_name = ballot.user.username if ballot.user else f"User {ballot.user_id}"
        s.delete(ballot)
        s.commit()
        flash(f"Deleted ballot from {user_name}", "success")

    return redirect(request.referrer or url_for("admin.ballots"))


@bp.post("/ballots/<int:ballot_id>/move")
@login_required
def move_ballot(ballot_id: int):
    """Move a ballot to a different poll"""
    require_admin()

    new_poll_id = request.form.get("new_poll_id", type=int)

    if not new_poll_id:
        flash("Poll ID required.", "danger")
        return redirect(url_for("admin.ballots"))

    with SessionLocal() as s:
        ballot = s.get(Ballot, ballot_id)
        new_poll = s.get(Poll, new_poll_id)

        if not ballot or not new_poll:
            flash("Ballot or poll not found.", "danger")
            return redirect(url_for("admin.ballots"))

        # Check if ballot already exists for this user in the new poll
        existing = s.execute(
            select(Ballot).where(
                Ballot.poll_id == new_poll_id,
                Ballot.user_id == ballot.user_id
            )
        ).scalar_one_or_none()

        if existing and existing.id != ballot_id:
            flash("User already has a ballot in that poll. Delete it first.", "danger")
            return redirect(url_for("admin.ballots"))

        old_poll_id = ballot.poll_id
        ballot.poll_id = new_poll_id
        s.commit()
        flash(f"Moved ballot from poll {old_poll_id} to poll {new_poll_id}", "success")

    return redirect(url_for("admin.ballots"))


@bp.get("/stats")
@login_required
def stats():
    """Statistics page"""
    require_admin()

    with SessionLocal() as s:
        # User stats
        total_users = s.execute(select(func.count(User.id))).scalar_one()
        admin_users = s.execute(select(func.count(User.id)).where(User.is_admin == True)).scalar_one()

        # Group stats
        total_groups = s.execute(select(func.count(Group.id))).scalar_one()
        public_groups = s.execute(select(func.count(Group.id)).where(Group.is_public == True)).scalar_one()
        private_groups = total_groups - public_groups

        # Poll stats
        total_polls = s.execute(select(func.count(Poll.id))).scalar_one()
        open_polls = s.execute(select(func.count(Poll.id)).where(Poll.is_open == True)).scalar_one()

        # Ballot stats
        total_ballots = s.execute(select(func.count(Ballot.id)).where(Ballot.submitted_at.isnot(None))).scalar_one()

        # Most active users (by ballot count)
        active_users = s.execute(
            select(User.username, func.count(Ballot.id).label('ballot_count'))
            .join(Ballot, Ballot.user_id == User.id)
            .where(Ballot.submitted_at.isnot(None))
            .group_by(User.id, User.username)
            .order_by(func.count(Ballot.id).desc())
            .limit(10)
        ).all()

        # Groups by member count
        groups_by_members = s.execute(
            select(Group.name, func.count(GroupMembership.id).label('member_count'))
            .join(GroupMembership, GroupMembership.group_id == Group.id)
            .group_by(Group.id, Group.name)
            .order_by(func.count(GroupMembership.id).desc())
        ).all()

    return render_template(
        "admin/stats.html",
        total_users=total_users,
        admin_users=admin_users,
        total_groups=total_groups,
        public_groups=public_groups,
        private_groups=private_groups,
        total_polls=total_polls,
        open_polls=open_polls,
        total_ballots=total_ballots,
        active_users=active_users,
        groups_by_members=groups_by_members
    )
