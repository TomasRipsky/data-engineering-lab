variable "env" {
  description = "Environment name."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env must be dev or prod."
  }
}

variable "project_id" {
  description = "GCP project created by `make bootstrap`."
  type        = string
}

variable "region" {
  description = "Region for the lake bucket and BigQuery datasets (GCS free tier regions only)."
  type        = string
  default     = "us-central1"
}

variable "github_repository" {
  description = "owner/name of the repository allowed to use Workload Identity Federation."
  type        = string
  default     = "TomasRipsky/data-engineering-lab"
}

variable "github_repository_id" {
  description = "Immutable numeric ID of that repository (a renamed or recreated repo gets a new one)."
  type        = string
  default     = "1396373223"
}

variable "query_quota_mib_per_day" {
  description = "Hard cap on BigQuery bytes scanned per day in this project, in MiB."
  type        = number
  default     = 51200
}
