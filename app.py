from flask import Flask, render_template
from flask_login import LoginManager, current_user
from models import db, User, Role

# Blueprints
from blueprints.cars import cars_bp
from blueprints.parts import parts_bp
from blueprints.work_orders import work_bp
from blueprints.users import users_bp
from blueprints.auth import auth_bp

# Load config class
from config import Config

app = Flask(__name__)
app.config.from_object(Config)   # <-- FIXED: loads SQLALCHEMY_DATABASE_URI correctly

# Initialize database
db.init_app(app)

# Make Role available in ALL templates
@app.context_processor
def inject_role():
    return dict(Role=Role)

# Login manager
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# -------------------------
# DASHBOARD ROUTES
# -------------------------

@app.route("/")
def dashboard():
    if not current_user.is_authenticated:
        return render_template("landing.html")

    if current_user.role == Role.MANAGER:
        return render_template("dashboard_manager.html")

    if current_user.role == Role.MECHANIC:
        return render_template("dashboard_mechanic.html")

    if current_user.role == Role.CLIENT:
        return render_template("dashboard_client.html")

    return "Unknown role"


# -------------------------
# REGISTER BLUEPRINTS
# -------------------------

app.register_blueprint(cars_bp)
app.register_blueprint(parts_bp)
app.register_blueprint(work_bp)
app.register_blueprint(users_bp)
app.register_blueprint(auth_bp)


# -------------------------
# RUN APP
# -------------------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
