use std::env;

#[derive(Clone, Debug)]
pub struct AppConfig {
    pub server: ServerConfig,
    pub aws: AwsConfig,
    pub sns: SnsConfig,
}

#[derive(Clone, Debug)]
pub struct ServerConfig {
    pub port: u16,
    pub max_upload_bytes: u64,
}

#[derive(Clone, Debug)]
pub struct AwsConfig {
    pub region: String,
    pub endpoint_url: Option<String>,
    pub s3_bucket: String,
    pub dynamodb_table: String,
    pub dynamodb_folders_table: String,
    pub dynamodb_versions_table: String,
    pub dynamodb_shares_table: String,
}

#[derive(Clone, Debug)]
pub struct SnsConfig {
    pub topic_arn: Option<String>,
}

impl AppConfig {
    pub fn from_env() -> Self {
        Self {
            server: ServerConfig::from_env(),
            aws: AwsConfig::from_env(),
            sns: SnsConfig::from_env(),
        }
    }

    /// Reject configuration the service cannot run with. An empty `S3_BUCKET`
    /// (e.g. a deploy whose Terraform output was unavailable) would otherwise
    /// start a "healthy" pod whose every upload fails with a storage error.
    pub fn validate(&self) -> Result<(), String> {
        self.aws.validate()
    }
}

impl ServerConfig {
    pub fn from_env() -> Self {
        Self {
            port: env::var("PORT")
                .unwrap_or_else(|_| "8082".into())
                .parse()
                .unwrap_or(8082),
            max_upload_bytes: env::var("MAX_UPLOAD_BYTES")
                .unwrap_or_else(|_| "104857600".into()) // 100 MB
                .parse()
                .unwrap_or(104_857_600),
        }
    }
}

impl AwsConfig {
    pub fn from_env() -> Self {
        Self {
            region: env::var("AWS_REGION").unwrap_or_else(|_| "us-east-1".into()),
            endpoint_url: env::var("AWS_ENDPOINT_URL").ok(),
            s3_bucket: env::var("S3_BUCKET").unwrap_or_else(|_| "otterworks-files".into()),
            dynamodb_table: env::var("DYNAMODB_TABLE")
                .unwrap_or_else(|_| "otterworks-file-metadata".into()),
            dynamodb_folders_table: env::var("DYNAMODB_FOLDERS_TABLE")
                .unwrap_or_else(|_| "otterworks-folders".into()),
            dynamodb_versions_table: env::var("DYNAMODB_VERSIONS_TABLE")
                .unwrap_or_else(|_| "otterworks-file-versions".into()),
            dynamodb_shares_table: env::var("DYNAMODB_SHARES_TABLE")
                .unwrap_or_else(|_| "otterworks-file-shares".into()),
        }
    }
}

impl AwsConfig {
    pub fn validate(&self) -> Result<(), String> {
        let required = [
            ("S3_BUCKET", &self.s3_bucket),
            ("DYNAMODB_TABLE", &self.dynamodb_table),
            ("DYNAMODB_FOLDERS_TABLE", &self.dynamodb_folders_table),
            ("DYNAMODB_VERSIONS_TABLE", &self.dynamodb_versions_table),
            ("DYNAMODB_SHARES_TABLE", &self.dynamodb_shares_table),
        ];
        for (name, value) in required {
            if value.trim().is_empty() {
                return Err(format!(
                    "{name} is set but empty; the deploy did not resolve it (for S3_BUCKET \
                     this is the Terraform output s3_file_bucket)"
                ));
            }
        }
        if self.s3_bucket != self.s3_bucket.trim() {
            return Err(format!(
                "S3_BUCKET {:?} has surrounding whitespace",
                self.s3_bucket
            ));
        }
        Ok(())
    }
}

impl SnsConfig {
    pub fn from_env() -> Self {
        Self {
            topic_arn: env::var("SNS_TOPIC_ARN").ok(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn aws_config(bucket: &str) -> AwsConfig {
        AwsConfig {
            region: "us-east-1".into(),
            endpoint_url: None,
            s3_bucket: bucket.into(),
            dynamodb_table: "otterworks-file-metadata".into(),
            dynamodb_folders_table: "otterworks-folders".into(),
            dynamodb_versions_table: "otterworks-file-versions".into(),
            dynamodb_shares_table: "otterworks-file-shares".into(),
        }
    }

    #[test]
    fn accepts_a_named_bucket() {
        assert!(aws_config("otterworks-files-dev").validate().is_ok());
    }

    #[test]
    fn rejects_an_empty_bucket() {
        let err = aws_config("").validate().unwrap_err();
        assert!(err.contains("S3_BUCKET"), "{err}");
        assert!(err.contains("s3_file_bucket"), "{err}");
    }

    #[test]
    fn rejects_a_whitespace_only_bucket() {
        assert!(aws_config("   ").validate().is_err());
    }

    #[test]
    fn rejects_a_padded_bucket_name() {
        assert!(aws_config(" otterworks-files-dev ").validate().is_err());
    }

    #[test]
    fn rejects_an_empty_table() {
        let mut cfg = aws_config("otterworks-files-dev");
        cfg.dynamodb_table = String::new();
        let err = cfg.validate().unwrap_err();
        assert!(err.contains("DYNAMODB_TABLE"), "{err}");
    }
}
