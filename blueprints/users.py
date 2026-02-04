from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from models import db, User, Role

users_bp = Blueprint("users", __name__, url_prefix="/users")

@users_bp.route("/", methods=["GET", "POST"])
@login_required
def manage_users():
    if current_user.role != Role.MANAGER:
        flash("Only managers can manage users.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role")

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(url_for("users.manage_users"))

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role=role
        )
        db.session.add(user)
        db.session.commit()
        flash("User created successfully.", "success")
        return redirect(url_for("users.manage_users"))

    users = User.query.order_by(User.id.desc()).all()
    return render_template("users.html", users=users, roles=[Role.MANAGER, Role.MECHANIC, Role.CLIENT])
