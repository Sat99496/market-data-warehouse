output "bronze_bucket_name" {
  description = "Put this in your .env as MDW_S3_BUCKET."
  value       = aws_s3_bucket.bronze.bucket
}

output "ingestion_user_name" {
  description = "IAM user the pipeline runs as. Create its access key with: aws iam create-access-key --user-name <this>"
  value       = aws_iam_user.ingestion.name
}

output "aws_region" {
  value = var.aws_region
}
