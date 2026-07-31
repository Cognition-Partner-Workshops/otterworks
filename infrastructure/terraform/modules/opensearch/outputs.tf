output "collection_arn" {
  description = "ARN of the OpenSearch Serverless collection"
  value       = aws_opensearchserverless_collection.this.arn
}

output "collection_id" {
  description = "ID of the OpenSearch Serverless collection"
  value       = aws_opensearchserverless_collection.this.id
}

output "collection_name" {
  description = "Name of the OpenSearch Serverless collection"
  value       = aws_opensearchserverless_collection.this.name
}

output "collection_endpoint" {
  description = "OpenSearch Serverless collection endpoint (set as OPENSEARCH_ENDPOINT)"
  value       = aws_opensearchserverless_collection.this.collection_endpoint
}

output "dashboard_endpoint" {
  description = "OpenSearch Dashboards endpoint for the collection"
  value       = aws_opensearchserverless_collection.this.dashboard_endpoint
}
