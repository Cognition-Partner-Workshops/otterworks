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
  description = "Run token stamped on every resource as a label and used in per-run names, for example gf-r1027a-after."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,22}[a-z0-9]$", var.run_token))
    error_message = "run_token must be 4-24 lowercase letters, digits or dashes, starting with a letter."
  }
}

variable "create_registry" {
  description = "Create the shared gf-fleet Artifact Registry repository. Set false for every run after the first in a project."
  type        = bool
  default     = true
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
  description = "Tag of the fleet-service and fleet-web images in Artifact Registry: the first 12 characters of the commit the gf-fleet-container workflow built."
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
