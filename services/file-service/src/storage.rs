use aws_sdk_s3::error::{DisplayErrorContext, ProvideErrorMetadata};
use aws_sdk_s3::presigning::PresigningConfig;
use bytes::Bytes;
use std::time::Duration;

use crate::config::AwsConfig;
use crate::errors::ServiceError;

/// S3 client for file blob operations.
#[derive(Clone)]
pub struct S3Client {
    pub client: aws_sdk_s3::Client,
    pub bucket: String,
}

impl S3Client {
    pub async fn new(config: &AwsConfig) -> Self {
        let mut aws_config_builder = aws_config::defaults(aws_config::BehaviorVersion::latest())
            .region(aws_config::Region::new(config.region.clone()));

        if let Some(endpoint) = &config.endpoint_url {
            aws_config_builder = aws_config_builder.endpoint_url(endpoint);
        }

        let aws_config = aws_config_builder.load().await;
        let s3_config = aws_sdk_s3::config::Builder::from(&aws_config)
            .force_path_style(true)
            .build();
        let client = aws_sdk_s3::Client::from_conf(s3_config);

        Self {
            client,
            bucket: config.s3_bucket.clone(),
        }
    }

    /// Check that the configured bucket exists and is reachable before the
    /// service accepts traffic, so a wrong `S3_BUCKET` fails the rollout
    /// instead of failing every upload. A missing bucket is final; other
    /// errors (endpoint not ready yet, transient network) are retried.
    pub async fn ensure_bucket_exists(&self) -> Result<(), ServiceError> {
        const ATTEMPTS: u32 = 5;
        const RETRY_DELAY: Duration = Duration::from_secs(3);

        let mut last_error = String::new();
        for attempt in 1..=ATTEMPTS {
            match self.client.head_bucket().bucket(&self.bucket).send().await {
                Ok(_) => {
                    tracing::info!(bucket = %self.bucket, "S3 bucket reachable");
                    return Ok(());
                }
                Err(e) => {
                    let not_found = e
                        .as_service_error()
                        .map(|se| se.is_not_found())
                        .unwrap_or(false);
                    last_error = DisplayErrorContext(&e).to_string();
                    tracing::warn!(
                        bucket = %self.bucket,
                        attempt,
                        max_attempts = ATTEMPTS,
                        error = %last_error,
                        "S3 HeadBucket failed"
                    );
                    if not_found {
                        break;
                    }
                    if attempt < ATTEMPTS {
                        tokio::time::sleep(RETRY_DELAY).await;
                    }
                }
            }
        }

        Err(ServiceError::S3Error(format!(
            "bucket '{}' is not accessible (check S3_BUCKET): {last_error}",
            self.bucket
        )))
    }

    /// Upload file content to S3.
    pub async fn upload_object(
        &self,
        key: &str,
        body: Bytes,
        content_type: &str,
    ) -> Result<(), ServiceError> {
        self.client
            .put_object()
            .bucket(&self.bucket)
            .key(key)
            .body(body.into())
            .content_type(content_type)
            .send()
            .await
            .map_err(|e| {
                let code = e.code().unwrap_or("unknown").to_string();
                tracing::error!(
                    bucket = %self.bucket,
                    key = %key,
                    s3_error_code = %code,
                    error = %DisplayErrorContext(&e),
                    "S3 PutObject failed"
                );
                ServiceError::S3Error(format!("upload failed: {code}"))
            })?;

        tracing::info!(key = %key, bucket = %self.bucket, "Uploaded object to S3");
        Ok(())
    }

    /// Download file content from S3.
    pub async fn download_object(&self, key: &str) -> Result<Bytes, ServiceError> {
        let resp = self
            .client
            .get_object()
            .bucket(&self.bucket)
            .key(key)
            .send()
            .await
            .map_err(|e| ServiceError::S3Error(format!("download failed: {e}")))?;

        let body = resp
            .body
            .collect()
            .await
            .map_err(|e| ServiceError::S3Error(format!("body read failed: {e}")))?;

        Ok(body.into_bytes())
    }

    /// Generate a presigned download URL.
    pub async fn presigned_download_url(
        &self,
        key: &str,
        expires_in_secs: u64,
    ) -> Result<String, ServiceError> {
        let presigning = PresigningConfig::expires_in(Duration::from_secs(expires_in_secs))
            .map_err(|e| ServiceError::S3Error(format!("presign config error: {e}")))?;

        let presigned = self
            .client
            .get_object()
            .bucket(&self.bucket)
            .key(key)
            .presigned(presigning)
            .await
            .map_err(|e| ServiceError::S3Error(format!("presign failed: {e}")))?;

        Ok(presigned.uri().to_string())
    }

    /// Delete an object from S3.
    pub async fn delete_object(&self, key: &str) -> Result<(), ServiceError> {
        self.client
            .delete_object()
            .bucket(&self.bucket)
            .key(key)
            .send()
            .await
            .map_err(|e| ServiceError::S3Error(format!("delete failed: {e}")))?;

        tracing::info!(key = %key, "Deleted object from S3");
        Ok(())
    }

    /// Copy an object within S3 (used for versioning).
    pub async fn copy_object(&self, source_key: &str, dest_key: &str) -> Result<(), ServiceError> {
        let copy_source = format!("{}/{}", self.bucket, source_key);
        self.client
            .copy_object()
            .bucket(&self.bucket)
            .copy_source(&copy_source)
            .key(dest_key)
            .send()
            .await
            .map_err(|e| ServiceError::S3Error(format!("copy failed: {e}")))?;

        tracing::info!(source = %source_key, dest = %dest_key, "Copied object in S3");
        Ok(())
    }
}
