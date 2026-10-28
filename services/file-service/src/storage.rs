use aws_sdk_s3::config::http::HttpResponse;
use aws_sdk_s3::error::{ProvideErrorMetadata, SdkError};
use aws_sdk_s3::presigning::PresigningConfig;
use aws_smithy_types::error::display::DisplayErrorContext;
use bytes::Bytes;
use std::time::Duration;

use crate::config::AwsConfig;
use crate::errors::ServiceError;

/// How long the readiness probe waits for S3 to answer `HeadBucket`.
const BUCKET_CHECK_TIMEOUT: Duration = Duration::from_secs(5);

/// S3 client for file blob operations.
#[derive(Clone)]
pub struct S3Client {
    pub client: aws_sdk_s3::Client,
    pub bucket: String,
}

/// Why the configured bucket cannot be used, as reported by `S3Client::verify_bucket`.
#[derive(Clone, Debug, PartialEq, Eq, serde::Serialize)]
pub struct BucketCheckFailure {
    pub bucket: String,
    /// AWS error code (`NoSuchBucket`, `NotFound`, `AccessDenied`, ...) when S3 answered.
    pub code: Option<String>,
    /// HTTP status of the S3 response when S3 answered.
    pub http_status: Option<u16>,
    pub detail: String,
}

impl std::fmt::Display for BucketCheckFailure {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "S3 bucket '{}' is not usable", self.bucket)?;
        if let Some(code) = &self.code {
            write!(f, " ({code}")?;
            if let Some(status) = self.http_status {
                write!(f, ", HTTP {status}")?;
            }
            write!(f, ")")?;
        } else if let Some(status) = self.http_status {
            write!(f, " (HTTP {status})")?;
        }
        write!(f, ": {}", self.detail)
    }
}

/// Build the error string for a failed S3 call: the operation, the bucket it
/// targeted, the AWS error code (`NoSuchBucket`, `AccessDenied`, ...) and the
/// HTTP status. Only ever logged — 5xx responses carry a generic message (see
/// `errors.rs`).
fn s3_failure<E>(operation: &str, bucket: &str, err: &SdkError<E, HttpResponse>) -> ServiceError
where
    E: std::error::Error + ProvideErrorMetadata + 'static,
{
    let code = err.code().map(str::to_owned);
    let status = sdk_http_status(err);
    record_s3_error(operation, code.as_deref());
    ServiceError::S3Error(format!(
        "{operation} on bucket '{bucket}' failed{}{}: {}",
        code.as_deref()
            .map(|c| format!(" [{c}]"))
            .unwrap_or_default(),
        status.map(|s| format!(" [HTTP {s}]")).unwrap_or_default(),
        sdk_error_detail(err)
    ))
}

/// One line of detail for a failed call: S3's own message when it answered
/// (the code and HTTP status are reported separately), otherwise the full
/// cause chain, which is where "connection refused" or a DNS failure lives.
fn sdk_error_detail<E>(err: &SdkError<E, HttpResponse>) -> String
where
    E: std::error::Error + ProvideErrorMetadata + 'static,
{
    match err {
        SdkError::ServiceError(_) => err
            .message()
            .map(str::to_owned)
            .unwrap_or_else(|| err.to_string()),
        other => DisplayErrorContext(other).to_string(),
    }
}

fn sdk_http_status<E>(err: &SdkError<E, HttpResponse>) -> Option<u16> {
    match err {
        SdkError::ServiceError(ctx) => Some(ctx.raw().status().as_u16()),
        SdkError::ResponseError(ctx) => Some(ctx.raw().status().as_u16()),
        _ => None,
    }
}

fn record_s3_error(operation: &str, code: Option<&str>) {
    crate::middleware::S3_ERRORS_TOTAL
        .with_label_values(&[operation, code.unwrap_or("unknown")])
        .inc();
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

    /// Check that the configured bucket exists and is reachable with the
    /// current credentials (`HeadBucket`). Used at startup and by `/ready`, so
    /// a misconfigured `S3_BUCKET` fails the rollout instead of every upload.
    pub async fn verify_bucket(&self) -> Result<(), BucketCheckFailure> {
        let head = self.client.head_bucket().bucket(&self.bucket).send();
        match tokio::time::timeout(BUCKET_CHECK_TIMEOUT, head).await {
            Ok(Ok(_)) => Ok(()),
            Ok(Err(err)) => {
                let code = err.code().map(str::to_owned);
                record_s3_error("head_bucket", code.as_deref());
                Err(BucketCheckFailure {
                    bucket: self.bucket.clone(),
                    code,
                    http_status: sdk_http_status(&err),
                    detail: sdk_error_detail(&err),
                })
            }
            Err(_) => {
                record_s3_error("head_bucket", Some("timeout"));
                Err(BucketCheckFailure {
                    bucket: self.bucket.clone(),
                    code: None,
                    http_status: None,
                    detail: format!(
                        "HeadBucket did not answer within {}s",
                        BUCKET_CHECK_TIMEOUT.as_secs()
                    ),
                })
            }
        }
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
            .map_err(|e| s3_failure("upload", &self.bucket, &e))?;

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
            .map_err(|e| s3_failure("download", &self.bucket, &e))?;

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
            .map_err(|e| s3_failure("presign", &self.bucket, &e))?;

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
            .map_err(|e| s3_failure("delete", &self.bucket, &e))?;

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
            .map_err(|e| s3_failure("copy", &self.bucket, &e))?;

        tracing::info!(source = %source_key, dest = %dest_key, "Copied object in S3");
        Ok(())
    }
}
