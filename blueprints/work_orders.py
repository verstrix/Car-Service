from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import or_

from models import db, WorkOrder, WorkOrderPart, Car, Part, User, Role

work_bp = Blueprint("work_orders", __name__, url_prefix="/work-orders")


@work_bp.route("/", methods=["GET", "POST"])
@login_required
def list_work_orders():

    # -----------------------------
    # CLIENT CREATES WORK ORDER
    # -----------------------------
    if request.method == "POST":
        if current_user.role != Role.CLIENT:
            flash("Само клиенти могат да създават работни поръчки.", "danger")
            return redirect(url_for("work_orders.list_work_orders"))

        # Get car details typed by client
        make = request.form.get("make")
        model = request.form.get("model")
        year = request.form.get("year")
        vin = request.form.get("vin")
        description = request.form.get("description")

        # Create a new car automatically
       # Check if VIN already exists
        existing_car = None
        if vin:
            existing_car = Car.query.filter_by(vin=vin).first()

        if existing_car:
            car = existing_car
        else:
            car = Car(
                vin=vin,
                make=make,
                model=model,
                year=int(year) if year else None,
                owner_name=current_user.username,
                owner_phone="N/A"
            )
            db.session.add(car)
            db.session.commit()


        flash("Работната поръчка е създадена успешно.", "success")
        return redirect(url_for("work_orders.list_work_orders"))

    # -----------------------------
    # LIST WORK ORDERS BASED ON ROLE
    # -----------------------------
    query = WorkOrder.query

    if current_user.role == Role.MECHANIC:
        # Mechanics see:
        # - Their assigned jobs
        # - Unassigned jobs
        query = query.filter(
            or_(
                WorkOrder.mechanic_id == current_user.id,
                WorkOrder.mechanic_id.is_(None)
            )
        )

    elif current_user.role == Role.CLIENT:
        query = query.filter_by(client_id=current_user.id)

    orders = query.order_by(WorkOrder.id.desc()).all()
    mechanics = User.query.filter_by(role=Role.MECHANIC).all()
    parts = Part.query.all()

    return render_template(
        "work_orders.html",
        orders=orders,
        mechanics=mechanics,
        parts=parts,
    )


# -----------------------------
# MANAGER ASSIGNS MECHANIC
# -----------------------------
@work_bp.route("/assign/<int:order_id>", methods=["POST"])
@login_required
def assign_mechanic(order_id):
    if current_user.role != Role.MANAGER:
        flash("Само мениджъри могат да назначават механици.", "danger")
        return redirect(url_for("work_orders.list_work_orders"))

    mechanic_id = int(request.form.get("mechanic_id"))
    order = WorkOrder.query.get_or_404(order_id)
    order.mechanic_id = mechanic_id
    order.status = "in_progress"
    db.session.commit()

    flash("Механикът е назначен успешно.", "success")
    return redirect(url_for("work_orders.list_work_orders"))


# -----------------------------
# MANAGER UPDATES STATUS
# -----------------------------
@work_bp.route("/status/<int:order_id>", methods=["POST"])
@login_required
def update_status(order_id):
    if current_user.role != Role.MANAGER:
        flash("Само мениджъри могат да обновяват статуса.", "danger")
        return redirect(url_for("work_orders.list_work_orders"))

    new_status = request.form.get("status")
    order = WorkOrder.query.get_or_404(order_id)

    order.status = new_status
    db.session.commit()

    flash("Статусът е обновен.", "success")
    return redirect(url_for("work_orders.list_work_orders"))


# -----------------------------
# MECHANIC COMPLETES WORK ORDER
# -----------------------------
@work_bp.route("/complete/<int:order_id>", methods=["POST"])
@login_required
def complete_order(order_id):
    if current_user.role != Role.MECHANIC:
        flash("Само механици могат да завършат работни поръчки.", "danger")
        return redirect(url_for("work_orders.list_work_orders"))

    order = WorkOrder.query.get_or_404(order_id)
    part_id = int(request.form.get("part_id"))
    quantity_used = int(request.form.get("quantity_used") or 0)

    # Deduct parts from inventory
    if quantity_used > 0:
        part = Part.query.get(part_id)
        if part and part.quantity >= quantity_used:
            part.quantity -= quantity_used
            wop = WorkOrderPart(
                work_order_id=order.id,
                part_id=part.id,
                quantity_used=quantity_used,
            )
            db.session.add(wop)
        else:
            flash("Няма достатъчно наличност за тази част.", "danger")
            return redirect(url_for("work_orders.list_work_orders"))

    order.status = "completed"
    db.session.commit()

    flash("Работната поръчка е завършена.", "success")
    return redirect(url_for("work_orders.list_work_orders"))

@work_bp.route("/view/<int:order_id>")
@login_required
def view_order(order_id):
    order = WorkOrder.query.get_or_404(order_id)
    car = order.car
    client = order.client
    mechanic = order.mechanic
    parts_used = order.parts  # WorkOrderPart entries
    mechanics = User.query.filter_by(role=Role.MECHANIC).all()

    return render_template(
        "work_order_details.html",
        order=order,
        car=car,
        client=client,
        mechanic=mechanic,
        parts_used=parts_used,
        mechanics=mechanics
    )

