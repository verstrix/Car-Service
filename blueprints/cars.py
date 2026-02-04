from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from models import db, Car, Role, WorkOrder, User

cars_bp = Blueprint("cars", __name__, url_prefix="/cars")


@cars_bp.route("/", methods=["GET", "POST"])
@login_required
def list_cars():

    # MANAGER: sees all cars
    if current_user.role == Role.MANAGER:
        cars = Car.query.order_by(Car.id.desc()).all()

    # MECHANIC: sees all cars (you can change this if needed)
    elif current_user.role == Role.MECHANIC:
        cars = Car.query.order_by(Car.id.desc()).all()

    # CLIENT: sees only their own cars
    else:
        cars = Car.query.filter_by(owner_name=current_user.username).order_by(Car.id.desc()).all()

    return render_template("cars.html", cars=cars)


@cars_bp.route("/<int:car_id>")
@login_required
def car_details(car_id):
    car = Car.query.get_or_404(car_id)

    # SECURITY: Clients can only view their own cars
    if current_user.role == Role.CLIENT and car.owner_name != current_user.username:
        flash("Нямате право да виждате този автомобил.", "danger")
        return redirect(url_for("cars.list_cars"))

    orders = WorkOrder.query.filter_by(car_id=car_id).all()
    mechanics = User.query.filter_by(role=Role.MECHANIC).all()

    return render_template(
        "car_details.html",
        car=car,
        orders=orders,
        mechanics=mechanics
    )
