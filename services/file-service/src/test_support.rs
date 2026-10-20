//! In-process fake AWS endpoints for unit tests. No network or AWS account is used.

use std::sync::{Arc, Mutex};
use std::time::Duration;

use aws_sdk_dynamodb::config::Credentials;
use aws_smithy_http_client::test_util::infallible_client_fn;
use aws_smithy_runtime_api::client::http::SharedHttpClient;
use aws_smithy_types::body::SdkBody;

use crate::config::{AwsClientTuning, AwsConfig};

#[derive(Clone, Debug)]
pub struct Call {
    pub service: &'static str,
    pub op: String,
    pub body: String,
}

impl Call {
    pub fn is(&self, service: &str, op: &str) -> bool {
        self.service == service && self.op == op
    }

    pub fn table(&self) -> Option<String> {
        let v: serde_json::Value = serde_json::from_str(&self.body).ok()?;
        v.get("TableName")?.as_str().map(str::to_string)
    }
}

pub type Calls = Arc<Mutex<Vec<Call>>>;

pub fn test_aws_config() -> AwsConfig {
    AwsConfig {
        region: "us-east-1".into(),
        endpoint_url: None,
        s3_bucket: "test-bucket".into(),
        dynamodb_table: "files".into(),
        dynamodb_folders_table: "folders".into(),
        dynamodb_versions_table: "versions".into(),
        dynamodb_shares_table: "shares".into(),
        tuning: AwsClientTuning {
            connect_timeout: Duration::from_millis(200),
            api_attempt_timeout: Duration::from_millis(100),
            api_operation_timeout: Duration::from_millis(400),
            s3_attempt_timeout: Duration::from_millis(100),
            s3_operation_timeout: Duration::from_millis(400),
            max_attempts: 2,
        },
    }
}

/// HTTP client that records each AWS call and answers with `respond(call)`.
pub fn fake_aws(
    respond: impl Fn(&Call) -> (u16, String) + Send + Sync + 'static,
) -> (SharedHttpClient, Calls) {
    let calls: Calls = Arc::new(Mutex::new(Vec::new()));
    let recorded = calls.clone();
    let client = infallible_client_fn(move |req: http::Request<SdkBody>| {
        let body = req
            .body()
            .bytes()
            .map(|b| String::from_utf8_lossy(b).to_string())
            .unwrap_or_default();
        let target = req
            .headers()
            .get("x-amz-target")
            .and_then(|v| v.to_str().ok())
            .map(str::to_string);
        let (service, op) = match target {
            Some(t) => (
                "dynamodb",
                t.rsplit('.').next().unwrap_or_default().to_string(),
            ),
            None if body.contains("Action=Publish") => ("sns", "Publish".to_string()),
            None => ("s3", req.method().to_string()),
        };
        let call = Call { service, op, body };
        let (status, resp) = respond(&call);
        recorded.lock().unwrap().push(call);
        http::Response::builder()
            .status(status)
            .header("content-type", "application/x-amz-json-1.0")
            .body(resp)
            .unwrap()
    });
    (client, calls)
}

pub async fn sdk_config(config: &AwsConfig, http: SharedHttpClient) -> aws_config::SdkConfig {
    config
        .sdk_config_loader()
        .http_client(http)
        .credentials_provider(Credentials::new(
            "test-akid",
            "test-secret",
            None,
            None,
            "test",
        ))
        .load()
        .await
}

pub fn ddb_ok() -> (u16, String) {
    (200, "{}".into())
}

pub fn ddb_error(kind: &str) -> (u16, String) {
    (
        400,
        format!(r#"{{"__type":"com.amazonaws.dynamodb.v20120810#{kind}","message":"{kind}"}}"#),
    )
}

pub fn s3_access_denied() -> (u16, String) {
    (
        403,
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?><Error><Code>AccessDenied</Code><Message>Access Denied</Message></Error>".into(),
    )
}

pub fn sns_ok() -> (u16, String) {
    (
        200,
        "<PublishResponse xmlns=\"http://sns.amazonaws.com/doc/2010-03-31/\"><PublishResult><MessageId>m-1</MessageId></PublishResult><ResponseMetadata><RequestId>r-1</RequestId></ResponseMetadata></PublishResponse>".into(),
    )
}

pub fn sns_denied() -> (u16, String) {
    (
        403,
        "<ErrorResponse xmlns=\"http://sns.amazonaws.com/doc/2010-03-31/\"><Error><Type>Sender</Type><Code>AuthorizationError</Code><Message>denied</Message></Error><RequestId>r-1</RequestId></ErrorResponse>".into(),
    )
}

pub fn events_count(event_type: &str, outcome: &str) -> u64 {
    crate::middleware::FILE_EVENTS_TOTAL
        .with_label_values(&[event_type, outcome])
        .get()
}
