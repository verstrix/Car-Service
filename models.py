from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class Role:
    MANAGER = "manager"
    MECHANIC = "mechanic"
    CLIENT = "client"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)

    def __repr__(self):
        return f"<User {self.username}>"

class Car(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vin = db.Column(db.String(50), unique=True, nullable=False)
    make = db.Column(db.String(80))
    model = db.Column(db.String(80))
    year = db.Column(db.Integer)
    owner_name = db.Column(db.String(120))
    owner_phone = db.Column(db.String(50))

class Part(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    part_number = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    quantity = db.Column(db.Integer, default=0)
    unit_price = db.Column(db.Float, default=0.0)

class WorkOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey("car.id"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    mechanic_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    status = db.Column(db.String(20), default="open")
    description = db.Column(db.Text)

    car = db.relationship("Car", backref="work_orders")
    client = db.relationship("User", foreign_keys=[client_id])
    mechanic = db.relationship("User", foreign_keys=[mechanic_id])

class WorkOrderPart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey("work_order.id"), nullable=False)
    part_id = db.Column(db.Integer, db.ForeignKey("part.id"), nullable=False)
    quantity_used = db.Column(db.Integer, nullable=False)

    work_order = db.relationship("WorkOrder", backref="parts_used")
    part = db.relationship("Part")
