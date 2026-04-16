from .route_support import register_template_helpers
from .routes_admin import register_admin_routes
from .routes_cars import register_car_routes
from .routes_main import register_main_routes
from .routes_orders import register_work_order_routes
from .routes_parts import register_part_routes


def register_routes(app):
    register_template_helpers(app)
    register_main_routes(app)
    register_car_routes(app)
    register_part_routes(app)
    register_work_order_routes(app)
    register_admin_routes(app)
