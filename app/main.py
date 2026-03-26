import os
import time

from flask import Flask, Blueprint, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
)

db = SQLAlchemy()

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency",
    ["endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
)
DB_STATUS = Gauge("db_connection_status", "Database connection (1=up 0=down)")
PIPELINE_RUNS_TOTAL = Counter(
    "pipeline_runs_total", "Pipeline runs created", ["status"]
)

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class PipelineRun(db.Model):
    __tablename__ = "pipeline_runs"

    id = db.Column(db.Integer, primary_key=True)
    sample_id = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default="queued")
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )
    duration = db.Column(db.Float, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "sample_id": self.sample_id,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "duration": self.duration,
        }

# ---------------------------------------------------------------------------
# Routes (blueprint so the factory can register them)
# ---------------------------------------------------------------------------


api = Blueprint("api", __name__)


@api.before_request
def _start_timer():
    request._start_time = time.time()


@api.after_request
def _record_metrics(response):
    if request.path == "/metrics":
        return response
    latency = time.time() - getattr(request, "_start_time", time.time())
    REQUEST_COUNT.labels(request.method, request.path, response.status_code).inc()
    REQUEST_LATENCY.labels(request.path).observe(latency)
    return response


@api.route("/health")
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        DB_STATUS.set(1)
        return jsonify(status="healthy", database="connected"), 200
    except Exception:
        DB_STATUS.set(0)
        return jsonify(status="unhealthy", database="disconnected"), 503


@api.route("/ready")
def ready():
    return jsonify(status="ready"), 200


@api.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


# ---- Pipeline-run CRUD ---------------------------------------------------

@api.route("/api/runs", methods=["GET"])
def list_runs():
    status_filter = request.args.get("status")
    query = PipelineRun.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    runs = query.order_by(PipelineRun.created_at.desc()).all()
    return jsonify([r.to_dict() for r in runs])


@api.route("/api/runs", methods=["POST"])
def create_run():
    data = request.get_json(force=True)
    if not data or "sample_id" not in data:
        return jsonify(error="sample_id is required"), 400
    run = PipelineRun(sample_id=data["sample_id"])
    db.session.add(run)
    db.session.commit()
    PIPELINE_RUNS_TOTAL.labels("queued").inc()
    return jsonify(run.to_dict()), 201


@api.route("/api/runs/<int:run_id>", methods=["GET"])
def get_run(run_id):
    run = db.get_or_404(PipelineRun, run_id)
    return jsonify(run.to_dict())


@api.route("/api/runs/<int:run_id>", methods=["PATCH"])
def update_run(run_id):
    run = db.get_or_404(PipelineRun, run_id)
    data = request.get_json(force=True)
    if "status" in data:
        run.status = data["status"]
        PIPELINE_RUNS_TOTAL.labels(data["status"]).inc()
    if "duration" in data:
        run.duration = data["duration"]
    db.session.commit()
    return jsonify(run.to_dict())


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app(config=None):
    application = Flask(__name__)

    application.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///:memory:"
    )
    application.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    if config:
        application.config.update(config)

    db.init_app(application)
    application.register_blueprint(api)

    with application.app_context():
        db.create_all()

    return application


# Gunicorn entry-point: app.main:app
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
