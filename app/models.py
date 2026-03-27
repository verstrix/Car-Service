from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from . import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='client')
    full_name = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    cars = db.relationship('Car', backref='user', lazy=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Car(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vin = db.Column(db.String(64), unique=True, nullable=False)
    registration_number = db.Column(db.String(32), unique=True)
    make = db.Column(db.String(80), nullable=False)
    model = db.Column(db.String(80), nullable=False)
    year = db.Column(db.Integer)
    owner_name = db.Column(db.String(120), nullable=False)
    owner_phone = db.Column(db.String(30))
    image_filename = db.Column(db.String(255))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship('WorkOrder', backref='car', lazy=True, cascade='all, delete-orphan')


class Part(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    part_number = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    min_quantity = db.Column(db.Integer, nullable=False, default=5)
    unit_price = db.Column(db.Float, nullable=False, default=0.0)
    description = db.Column(db.Text)
    image_filename = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    order_links = db.relationship('WorkOrderPart', backref='part', lazy=True, cascade='all, delete-orphan')


class WorkOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), nullable=False, default='open')
    notes = db.Column(db.Text)
    labor_cost = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    car_id = db.Column(db.Integer, db.ForeignKey('car.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    mechanic_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    client = db.relationship('User', foreign_keys=[client_id], backref='client_orders')
    mechanic = db.relationship('User', foreign_keys=[mechanic_id], backref='assigned_orders')
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_orders')
    parts = db.relationship('WorkOrderPart', backref='work_order', lazy=True, cascade='all, delete-orphan')

    @property
    def total_parts_cost(self):
        return round(sum((link.unit_price_snapshot or 0) * link.quantity_used for link in self.parts), 2)

    @property
    def total_cost(self):
        return round((self.labor_cost or 0) + self.total_parts_cost, 2)


class WorkOrderPart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey('work_order.id'), nullable=False)
    part_id = db.Column(db.Integer, db.ForeignKey('part.id'), nullable=False)
    quantity_used = db.Column(db.Integer, nullable=False, default=1)
    unit_price_snapshot = db.Column(db.Float, nullable=False, default=0.0)
