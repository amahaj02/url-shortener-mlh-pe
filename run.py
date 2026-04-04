import os

from waitress import serve

from app import create_app

app = create_app()


def _int_env(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = _int_env("PORT", 5000)

    if os.name == "nt":
        serve(
            app,
            host=host,
            port=port,
            threads=_int_env("WAITRESS_THREADS", 8),
        )
    else:
        app.run(debug=app.config["DEBUG"], host=host, port=port)
