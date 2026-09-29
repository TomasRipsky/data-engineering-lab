resource "google_service_account" "pipeline" {
  account_id   = "pitwall-pipeline"
  display_name = "pitwall pipeline (${var.env})"

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket_iam_member" "pipeline_lake" {
  bucket = google_storage_bucket.raw.name
  role   = "roles/storage.objectAdmin"
  member = google_service_account.pipeline.member
}

resource "google_bigquery_dataset_iam_member" "pipeline_datasets" {
  for_each   = google_bigquery_dataset.layers
  dataset_id = each.value.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = google_service_account.pipeline.member
}

resource "google_project_iam_member" "pipeline_jobs" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = google_service_account.pipeline.member
}

resource "google_service_account" "dashboard" {
  count        = var.env == "prod" ? 1 : 0
  account_id   = "pitwall-dashboard"
  display_name = "pitwall dashboard reader"

  depends_on = [google_project_service.apis]
}

resource "google_bigquery_dataset_iam_member" "dashboard_marts" {
  count      = var.env == "prod" ? 1 : 0
  dataset_id = google_bigquery_dataset.layers["marts"].dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = google_service_account.dashboard[0].member
}

resource "google_project_iam_member" "dashboard_jobs" {
  count   = var.env == "prod" ? 1 : 0
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = google_service_account.dashboard[0].member
}

# Deleted pools stay reserved for 30 days: a suffix lets destroy → apply work immediately.
resource "random_id" "pool" {
  byte_length = 2
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-${random_id.pool.hex}"
  display_name              = "GitHub Actions"

  depends_on = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions"
  display_name                       = "GitHub Actions OIDC"

  attribute_mapping = merge(
    {
      "google.subject"       = "assertion.sub"
      "attribute.repository" = "assertion.repository"
    },
    var.env == "prod" ? { "attribute.environment" = "assertion.environment" } : {},
  )

  # Without a condition any GitHub repository could exchange tokens here.
  attribute_condition = join(" && ", compact([
    "assertion.repository_id == '${var.github_repository_id}'",
    var.env == "prod" ? "assertion.environment == 'prod'" : "",
  ]))

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

locals {
  github_principal = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

resource "google_service_account_iam_member" "pipeline_wif" {
  service_account_id = google_service_account.pipeline.name
  role               = "roles/iam.workloadIdentityUser"
  member             = local.github_principal
}

resource "google_service_account_iam_member" "dashboard_wif" {
  count              = var.env == "prod" ? 1 : 0
  service_account_id = google_service_account.dashboard[0].name
  role               = "roles/iam.workloadIdentityUser"
  member             = local.github_principal
}
