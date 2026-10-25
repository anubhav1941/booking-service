import os


class Settings:
    """All runtime config comes from environment variables.
    In Kubernetes these are injected from a ConfigMap and a Secret."""

    service_name: str = "booking-service"
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://booking:booking@localhost:5433/booking_db",
    )
    # In Kubernetes this is the ClusterIP Service DNS name: http://inventory-service
    inventory_url: str = os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8001").rstrip("/")
    inventory_timeout_s: float = float(os.getenv("INVENTORY_TIMEOUT_SECONDS", "3"))
    inventory_retries: int = int(os.getenv("INVENTORY_RETRIES", "3"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    instance_name: str = os.getenv("POD_NAME", os.getenv("HOSTNAME", "local"))


settings = Settings()
