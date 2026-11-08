#############################################################################
# Market Data Warehouse - AWS foundation
#
# Creates:
#   1. A private, encrypted, versioned S3 bucket for the Bronze layer
#   2. A least-privilege IAM user + policy for the ingestion pipeline
#   3. A monthly cost budget with email alerts
#
# All of this sits inside the AWS free tier for a project of this size.
#############################################################################

data "aws_caller_identity" "current" {}

locals {
  # Bucket names are global across all AWS accounts, so the account ID keeps it unique.
  bucket_name = "mdw-bronze-${data.aws_caller_identity.current.account_id}"
}

# ---------------------------------------------------------------------------
# 1. Bronze data lake bucket
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "bronze" {
  bucket = local.bucket_name
}

# Keep previous versions so an accidental overwrite or delete can be recovered.
resource "aws_s3_bucket_versioning" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Encrypt every object at rest.
resource "aws_s3_bucket_server_side_encryption_configuration" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# The bucket can never be made public, even by mistake.
resource "aws_s3_bucket_public_access_block" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Delete old file versions after N days so storage costs stay near zero.
resource "aws_s3_bucket_lifecycle_configuration" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  rule {
    id     = "expire-old-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  depends_on = [aws_s3_bucket_versioning.bronze]
}

# ---------------------------------------------------------------------------
# 2. Least-privilege identity for the ingestion pipeline
# ---------------------------------------------------------------------------
# The pipeline can only list this one bucket and read/write files inside it.
# It cannot touch any other bucket or AWS service.
data "aws_iam_policy_document" "ingestion" {
  statement {
    sid       = "ListBronzeBucket"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.bronze.arn]
  }

  statement {
    sid       = "ReadWriteBronzeObjects"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.bronze.arn}/*"]
  }
}

resource "aws_iam_policy" "ingestion" {
  name        = "mdw-ingestion-bronze-access"
  description = "Market Data Warehouse: read/write access to the Bronze bucket only"
  policy      = data.aws_iam_policy_document.ingestion.json
}

resource "aws_iam_user" "ingestion" {
  name = "mdw-ingestion"
}

resource "aws_iam_user_policy_attachment" "ingestion" {
  user       = aws_iam_user.ingestion.name
  policy_arn = aws_iam_policy.ingestion.arn
}

# ---------------------------------------------------------------------------
# 3. Cost guardrail
# ---------------------------------------------------------------------------
resource "aws_budgets_budget" "monthly" {
  name         = "mdw-monthly-budget"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Email when actual spend passes 80% of the budget...
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }

  # ...and when AWS forecasts the month will exceed it.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_email]
  }
}
