variable "aws_region" {
  description = "AWS region to create everything in (eu-west-2 = London)."
  type        = string
  default     = "eu-west-2"
}

variable "owner" {
  description = "Your name or handle, added as a tag on every resource."
  type        = string
  default     = "Sat99496"
}

variable "budget_email" {
  description = "Email address that receives cost alerts."
  type        = string
}

variable "monthly_budget_usd" {
  description = "Monthly spending limit in USD that triggers alerts. Keep it small for a portfolio project."
  type        = number
  default     = 5
}

variable "noncurrent_version_days" {
  description = "Days to keep old versions of overwritten files before deleting them (keeps storage costs near zero)."
  type        = number
  default     = 30
}
