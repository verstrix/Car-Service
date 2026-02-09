from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from models import db, Part, Role
from sqlalchemy.exc import IntegrityError
from models import WorkOrderPart

parts_bp = Blueprint("parts", __name__, url_prefix="/parts")

@parts_bp.route("/", methods=["GET", "POST"])
@login_required
def list_parts():
    if request.method == "POST":
        if current_user.role != Role.MANAGER:
            flash("Само мениджъри могат да управляват инвентара.", "danger")
            return redirect(url_for("parts.list_parts"))

        part_number = (request.form.get("part_number") or "").strip()
        name = (request.form.get("name") or "").strip()
        description = request.form.get("description")
        try:
            quantity = int(request.form.get("quantity") or 0)
        except (ValueError, TypeError):
            quantity = 0
        try:
            unit_price = float(request.form.get("unit_price") or 0)
        except (ValueError, TypeError):
            unit_price = 0.0

        if not part_number or not name:
            flash("Номер и име на частта са задължителни.", "danger")
            return redirect(url_for("parts.list_parts"))

        part = Part(
            part_number=part_number,
            name=name,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
        )
        db.session.add(part)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Част с този номер вече съществува.", "danger")
            return redirect(url_for("parts.list_parts"))
        flash("Частта е добавена.", "success")
        return redirect(url_for("parts.list_parts"))

    parts = Part.query.order_by(Part.id.desc()).all()
    return render_template("parts.html", parts=parts)


@parts_bp.route('/<int:part_id>')
@login_required
def part_details(part_id):
    part = Part.query.get_or_404(part_id)
    return render_template('part_details.html', part=part)


@parts_bp.route("/delete/<int:part_id>", methods=["POST"])
@login_required
def delete_part(part_id):
    if current_user.role != Role.MANAGER:
        flash("Само мениджъри могат да изтриват части.", "danger")
        return redirect(url_for("parts.list_parts"))

    part = Part.query.get_or_404(part_id)

    # Prevent deletion if part was used in any work order
    used = WorkOrderPart.query.filter_by(part_id=part.id).first()
    if used:
        flash("Не може да изтриете частта — вече е използвана в работни поръчки.", "danger")
        return redirect(url_for("parts.list_parts"))

    db.session.delete(part)
    db.session.commit()
    flash("Частта е изтрита.", "success")
    return redirect(url_for("parts.list_parts"))
