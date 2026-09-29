locals {
  apis     = ["bigquery.googleapis.com", "storage.googleapis.com", "iam.googleapis.com", "iamcredentials.googleapis.com", "sts.googleapis.com"]
  datasets = ["raw", "staging", "intermediate", "marts"]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

# The lake is regenerable from OpenF1, so destroy may delete it with its contents (ADR 0005).
resource "google_storage_bucket" "raw" {
  name                        = "${var.project_id}-raw"
  location                    = upper(var.region)
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true

  depends_on = [google_project_service.apis]
}

resource "google_bigquery_dataset" "layers" {
  for_each                   = toset(local.datasets)
  dataset_id                 = each.value
  location                   = var.region
  delete_contents_on_destroy = true

  depends_on = [google_project_service.apis]
}

# A budget alert only warns; this quota stops runaway queries.
resource "google_service_usage_consumer_quota_override" "bigquery_query_per_day" {
  provider       = google-beta
  service        = "bigquery.googleapis.com"
  metric         = urlencode("bigquery.googleapis.com/quota/query/usage")
  limit          = urlencode("/d/project")
  override_value = var.query_quota_mib_per_day
  force          = true

  depends_on = [google_project_service.apis]
}
