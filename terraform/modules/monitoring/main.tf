resource "google_logging_metric" "error_count" {
  name   = "${var.app_name}-error-count"
  filter = "resource.type=\"k8s_container\" AND resource.labels.namespace_name=\"production\" AND severity>=ERROR"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_monitoring_alert_policy" "error_rate" {
  display_name = "${var.app_name} - High Error Rate"
  combiner     = "OR"

  conditions {
    display_name = "Error count exceeds threshold"

    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.error_count.name}\" AND resource.type=\"k8s_container\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 10

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }
}

resource "google_monitoring_alert_policy" "pod_restart" {
  display_name = "${var.app_name} - Pod Restart Loop"
  combiner     = "OR"

  conditions {
    display_name = "Pod restart count exceeds threshold"

    condition_threshold {
      filter          = "metric.type=\"kubernetes.io/container/restart_count\" AND resource.type=\"k8s_container\" AND resource.labels.namespace_name=\"production\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 3

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }
}
