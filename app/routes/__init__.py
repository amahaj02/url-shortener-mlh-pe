def register_routes(app):
    from app.routes.events import events_bp
    from app.routes.maintenance import maintenance_bp
    from app.routes.urls import redirect_bp, urls_bp
    from app.routes.users import users_bp

    app.register_blueprint(users_bp)
    app.register_blueprint(urls_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(redirect_bp)
