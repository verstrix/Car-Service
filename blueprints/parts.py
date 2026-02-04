from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from models import db, Part, Role

parts_bp = Blueprint("parts", __name__, url_prefix="/parts")

@parts_bp.route("/", methods=["GET", "POST"])
@login_required
def list_parts():
    if request.method == "POST":
        if current_user.role != Role.MANAGER:
            flash("Само мениджъри могат да управляват инвентара.", "danger")
            return redirect(url_for("parts.list_parts"))

        part_number = request.form.get("part_number")
        name = request.form.get("name")
        description = request.form.get("description")
        quantity = int(request.form.get("quantity") or 0)
        unit_price = float(request.form.get("unit_price") or 0)

        part = Part(
            part_number=part_number,
            name=name,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
        )
        db.session.add(part)
        db.session.commit()
        flash("Частта е добавена.", "success")
        return redirect(url_for("parts.list_parts"))

    parts = Part.query.order_by(Part.id.desc()).all()
    return render_template("parts.html", parts=parts)
