variable "project_id" {
  description = "Existing Google Cloud project that hosts the global fleet app. This configuration never creates a project."
  type        = string
}

variable "region" {
  description = "Region for Cloud Run, Cloud SQL and Artifact Registry."
  type        = string
  default     = "europe-west3"
}

variable "run_token" {
  description = "Run token stamped on every resource as a label, for example gf-r1027a-after."
  type        = string
}

variable "expires_at" {
  description = "Expiry date label, YYYY-MM-DD."
  type        = string
}

variable "country_profile" {
  description = "Country profile the service starts with."
  type        = string
  default     = "de"
}

variable "image_tag" {
  description = "Tag of the fleet-service and fleet-web images in Artifact Registry."
  type        = string
}

variable "db_tier" {
  description = "Cloud SQL machine tier."
  type        = string
  default     = "db-f1-micro"
}

variable "deletion_protection" {
  description = "Protect the Cloud SQL instance from destroy."
  type        = bool
  default     = false
}
