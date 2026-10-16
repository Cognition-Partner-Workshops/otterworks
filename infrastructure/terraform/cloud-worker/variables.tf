variable "devin_webhook_url" {
  description = "Devin automation webhook URL the EventBridge API destination posts to"
  type        = string
  default     = "https://example.invalid/webhook"
}

variable "devin_webhook_secret" {
  description = "Value sent in the X-Webhook-Secret header to the Devin webhook"
  type        = string
  sensitive   = true
  default     = "replace-me"
}

variable "tenant_namespace" {
  description = "Kubernetes namespace of the cloud-worker tenant"
  type        = string
  default     = "otterworks-cloud-worker"
}

variable "run_token" {
  description = "Run token written to the run_token tag"
  type        = string
  default     = "cw"
}

variable "expires" {
  description = "Expiry written to the expires tag"
  type        = string
  default     = "never"
}

variable "eks_cluster" {
  description = "EKS cluster whose OIDC provider the IRSA roles trust"
  type        = string
  default     = "otterworks-dev"
}
