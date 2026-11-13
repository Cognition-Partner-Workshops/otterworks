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
            .map_err(|e| ServiceError::S3Error(format!("upload failed: {e}")))?;

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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_support::{FakeAws, TEST_BUCKET};

    const S3_ERROR: &str = r#"<?xml version="1.0" encoding="UTF-8"?><Error><Code>AccessDenied</Code><Message>Access Denied</Message><RequestId>r</RequestId></Error>"#;

    fn assert_s3_error(err: ServiceError, prefix: &str) {
        match err {
            ServiceError::S3Error(msg) => assert!(msg.starts_with(prefix), "{msg}"),
            other => panic!("expected S3Error, got {other:?}"),
        }
    }

    #[actix_rt::test]
    async fn upload_puts_object_with_content_type() {
        let fake = FakeAws::new();
        fake.respond("PUT", 200, "");
        fake.s3_client()
            .upload_object("files/o/f", Bytes::from_static(b"hello"), "text/plain")
            .await
            .unwrap();

        let reqs = fake.requests_for("PUT");
        assert_eq!(reqs.len(), 1);
        assert!(
            reqs[0].uri.contains(&format!("/{TEST_BUCKET}/files/o/f")),
            "{}",
            reqs[0].uri
        );
        assert_eq!(reqs[0].header("content-type"), Some("text/plain"));
    }

    #[actix_rt::test]
    async fn upload_failure_maps_to_s3_error() {
        let fake = FakeAws::new();
        fake.respond("PUT", 403, S3_ERROR);
        let err = fake
            .s3_client()
            .upload_object("k", Bytes::from_static(b"x"), "text/plain")
            .await
            .unwrap_err();
        assert_s3_error(err, "upload failed");
    }

    #[actix_rt::test]
    async fn download_returns_object_body() {
        let fake = FakeAws::new();
        fake.respond("GET", 200, "file-contents");
        let body = fake.s3_client().download_object("files/o/f").await.unwrap();
        assert_eq!(&body[..], b"file-contents");
        let reqs = fake.requests_for("GET");
        assert!(reqs[0].uri.contains(&format!("/{TEST_BUCKET}/files/o/f")));
    }

    #[actix_rt::test]
    async fn download_failure_maps_to_s3_error() {
        let fake = FakeAws::new();
        fake.respond(
            "GET",
            404,
            r#"<Error><Code>NoSuchKey</Code><Message>missing</Message></Error>"#,
        );
        let err = fake.s3_client().download_object("k").await.unwrap_err();
        assert_s3_error(err, "download failed");
    }

    #[actix_rt::test]
    async fn presigned_url_is_generated_locally() {
        let fake = FakeAws::new();
        let url = fake
            .s3_client()
            .presigned_download_url("files/o/f", 3600)
            .await
            .unwrap();
        assert!(url.contains(&format!("/{TEST_BUCKET}/files/o/f?")), "{url}");
        assert!(url.contains("X-Amz-Expires=3600"), "{url}");
        assert!(url.contains("X-Amz-Signature="), "{url}");
        assert!(fake.requests().is_empty(), "presigning must not call S3");
    }

    #[actix_rt::test]
    async fn presigned_url_rejects_expiry_over_one_week() {
        let fake = FakeAws::new();
        let err = fake
            .s3_client()
            .presigned_download_url("k", 8 * 24 * 3600)
            .await
            .unwrap_err();
        assert_s3_error(err, "presign config error");
    }

    #[actix_rt::test]
    async fn delete_object_sends_delete() {
        let fake = FakeAws::new();
        fake.respond("DELETE", 204, "");
        fake.s3_client().delete_object("files/o/f").await.unwrap();
        let reqs = fake.requests_for("DELETE");
        assert_eq!(reqs.len(), 1);
        assert!(reqs[0].uri.contains(&format!("/{TEST_BUCKET}/files/o/f")));
    }

    #[actix_rt::test]
    async fn delete_failure_maps_to_s3_error() {
        let fake = FakeAws::new();
        fake.respond("DELETE", 403, S3_ERROR);
        let err = fake.s3_client().delete_object("k").await.unwrap_err();
        assert_s3_error(err, "delete failed");
    }

    #[actix_rt::test]
    async fn copy_object_uses_bucket_qualified_source() {
        let fake = FakeAws::new();
        fake.respond(
            "PUT",
            200,
            r#"<CopyObjectResult><ETag>"e"</ETag><LastModified>2024-01-01T00:00:00.000Z</LastModified></CopyObjectResult>"#,
        );
        fake.s3_client()
            .copy_object("files/o/f", "files/o/f.v2")
            .await
            .unwrap();
        let req = &fake.requests_for("PUT")[0];
        assert!(req.uri.contains(&format!("/{TEST_BUCKET}/files/o/f.v2")));
        assert_eq!(
            req.header("x-amz-copy-source"),
            Some(format!("{TEST_BUCKET}/files/o/f").as_str())
        );
    }

    #[actix_rt::test]
    async fn copy_failure_maps_to_s3_error() {
        let fake = FakeAws::new();
        fake.respond("PUT", 403, S3_ERROR);
        let err = fake.s3_client().copy_object("a", "b").await.unwrap_err();
        assert_s3_error(err, "copy failed");
    }
}
