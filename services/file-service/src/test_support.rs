//! Offline fakes for the AWS SDK clients, used only by unit tests.
//!
//! Every SDK client is built with static credentials, retries disabled and an
//! in-process HTTP client that answers from a queue of canned responses and
//! records each request, so tests never touch the network.

use std::collections::{HashMap, VecDeque};
use std::sync::{Arc, Mutex};

use aws_smithy_http_client::test_util::infallible_client_fn;
use chrono::{DateTime, Utc};
use serde_json::{json, Value};
use uuid::Uuid;

use crate::metadata::MetadataClient;
use crate::storage::S3Client;

pub const TEST_BUCKET: &str = "test-bucket";

#[derive(Debug, Clone)]
pub struct CapturedRequest {
    pub method: String,
    pub uri: String,
    pub op: String,
    pub headers: HashMap<String, String>,
    pub body: String,
}

impl CapturedRequest {
    pub fn header(&self, name: &str) -> Option<&str> {
        self.headers.get(&name.to_lowercase()).map(String::as_str)
    }

    pub fn json(&self) -> Value {
        serde_json::from_str(&self.body).expect("request body is JSON")
    }

    pub fn form(&self) -> HashMap<String, String> {
        actix_web::web::Query::<HashMap<String, String>>::from_query(&self.body)
            .expect("request body is form-encoded")
            .into_inner()
    }
}

type Canned = (u16, String);

#[derive(Clone, Default)]
pub struct FakeAws {
    responses: Arc<Mutex<HashMap<String, VecDeque<Canned>>>>,
    requests: Arc<Mutex<Vec<CapturedRequest>>>,
}

/// Key used to route a request to its canned response: the DynamoDB
/// `X-Amz-Target` operation, the SNS/Query `Action`, or the HTTP method (S3).
fn operation_key(req: &http::Request<aws_smithy_types::body::SdkBody>, body: &str) -> String {
    if let Some(target) = req
        .headers()
        .get("x-amz-target")
        .and_then(|v| v.to_str().ok())
    {
        return target.rsplit('.').next().unwrap_or(target).to_string();
    }
    if let Some(action) = body.split('&').find_map(|kv| kv.strip_prefix("Action=")) {
        return action.to_string();
    }
    req.method().as_str().to_string()
}

impl FakeAws {
    pub fn new() -> Self {
        Self::default()
    }

    /// Queue a response for the next request whose operation key is `op`.
    pub fn respond(&self, op: &str, status: u16, body: impl Into<String>) -> &Self {
        self.responses
            .lock()
            .unwrap()
            .entry(op.to_string())
            .or_default()
            .push_back((status, body.into()));
        self
    }

    pub fn respond_json(&self, op: &str, body: Value) -> &Self {
        self.respond(op, 200, body.to_string())
    }

    pub fn dynamo_error(&self, op: &str, error_type: &str) -> &Self {
        self.respond(
            op,
            400,
            json!({
                "__type": format!("com.amazonaws.dynamodb.v20120810#{error_type}"),
                "message": format!("{error_type} raised by fake"),
            })
            .to_string(),
        )
    }

    pub fn requests(&self) -> Vec<CapturedRequest> {
        self.requests.lock().unwrap().clone()
    }

    pub fn requests_for(&self, op: &str) -> Vec<CapturedRequest> {
        self.requests().into_iter().filter(|r| r.op == op).collect()
    }

    fn http_client(&self) -> aws_sdk_s3::config::SharedHttpClient {
        let responses = self.responses.clone();
        let requests = self.requests.clone();
        infallible_client_fn(move |req: http::Request<aws_smithy_types::body::SdkBody>| {
            let body = req
                .body()
                .bytes()
                .map(|b| String::from_utf8_lossy(b).to_string())
                .unwrap_or_default();
            let op = operation_key(&req, &body);
            let headers = req
                .headers()
                .iter()
                .map(|(k, v)| {
                    (
                        k.as_str().to_lowercase(),
                        v.to_str().unwrap_or_default().to_string(),
                    )
                })
                .collect();
            requests.lock().unwrap().push(CapturedRequest {
                method: req.method().to_string(),
                uri: req.uri().to_string(),
                op: op.clone(),
                headers,
                body,
            });
            let (status, body) = responses
                .lock()
                .unwrap()
                .get_mut(&op)
                .and_then(VecDeque::pop_front)
                .unwrap_or_else(|| {
                    (
                        500,
                        json!({
                            "__type": "UnexpectedRequest",
                            "message": format!("no canned response for {op}"),
                        })
                        .to_string(),
                    )
                });
            http::Response::builder().status(status).body(body).unwrap()
        })
    }

    pub fn dynamodb(&self) -> aws_sdk_dynamodb::Client {
        use aws_sdk_dynamodb::config::{retry::RetryConfig, BehaviorVersion, Credentials, Region};
        let conf = aws_sdk_dynamodb::Config::builder()
            .behavior_version(BehaviorVersion::latest())
            .region(Region::new("us-east-1"))
            .credentials_provider(Credentials::new("test", "test", None, None, "test"))
            .retry_config(RetryConfig::disabled())
            .http_client(self.http_client())
            .build();
        aws_sdk_dynamodb::Client::from_conf(conf)
    }

    pub fn s3(&self) -> aws_sdk_s3::Client {
        use aws_sdk_s3::config::{retry::RetryConfig, BehaviorVersion, Credentials, Region};
        let conf = aws_sdk_s3::Config::builder()
            .behavior_version(BehaviorVersion::latest())
            .region(Region::new("us-east-1"))
            .credentials_provider(Credentials::new("test", "test", None, None, "test"))
            .retry_config(RetryConfig::disabled())
            .force_path_style(true)
            .http_client(self.http_client())
            .build();
        aws_sdk_s3::Client::from_conf(conf)
    }

    pub fn sns(&self) -> aws_sdk_sns::Client {
        use aws_sdk_sns::config::{retry::RetryConfig, BehaviorVersion, Credentials, Region};
        let conf = aws_sdk_sns::Config::builder()
            .behavior_version(BehaviorVersion::latest())
            .region(Region::new("us-east-1"))
            .credentials_provider(Credentials::new("test", "test", None, None, "test"))
            .retry_config(RetryConfig::disabled())
            .http_client(self.http_client())
            .build();
        aws_sdk_sns::Client::from_conf(conf)
    }

    pub fn metadata_client(&self) -> MetadataClient {
        MetadataClient {
            client: self.dynamodb(),
            files_table: "files".into(),
            folders_table: "folders".into(),
            versions_table: "versions".into(),
            shares_table: "shares".into(),
        }
    }

    pub fn s3_client(&self) -> S3Client {
        S3Client {
            client: self.s3(),
            bucket: TEST_BUCKET.into(),
        }
    }
}

// -- DynamoDB JSON fixtures --

pub fn ts(rfc3339: &str) -> DateTime<Utc> {
    DateTime::parse_from_rfc3339(rfc3339)
        .unwrap()
        .with_timezone(&Utc)
}

pub fn file_item(id: Uuid, owner: Uuid, name: &str, updated_at: &str, is_trashed: bool) -> Value {
    json!({
        "id": {"S": id.to_string()},
        "name": {"S": name},
        "mime_type": {"S": "text/plain"},
        "size_bytes": {"N": "42"},
        "s3_key": {"S": format!("files/{owner}/{id}")},
        "owner_id": {"S": owner.to_string()},
        "version": {"N": "1"},
        "is_trashed": {"BOOL": is_trashed},
        "created_at": {"S": updated_at},
        "updated_at": {"S": updated_at},
    })
}

pub fn folder_item(id: Uuid, owner: Uuid, name: &str, parent: Option<Uuid>) -> Value {
    let mut item = json!({
        "id": {"S": id.to_string()},
        "name": {"S": name},
        "owner_id": {"S": owner.to_string()},
        "created_at": {"S": "2024-01-01T00:00:00+00:00"},
        "updated_at": {"S": "2024-01-02T00:00:00+00:00"},
    });
    if let Some(p) = parent {
        item["parent_id"] = json!({"S": p.to_string()});
    }
    item
}

pub fn version_item(file_id: Uuid, version: u32, created_by: Uuid) -> Value {
    json!({
        "file_id": {"S": file_id.to_string()},
        "version": {"N": version.to_string()},
        "s3_key": {"S": format!("files/{file_id}/v{version}")},
        "size_bytes": {"N": "7"},
        "created_by": {"S": created_by.to_string()},
        "created_at": {"S": "2024-01-01T00:00:00+00:00"},
    })
}

pub fn share_item(
    id: Uuid,
    file_id: Uuid,
    shared_with: Uuid,
    permission: &str,
    shared_by: Uuid,
    created_at: &str,
) -> Value {
    json!({
        "id": {"S": id.to_string()},
        "file_id": {"S": file_id.to_string()},
        "shared_with": {"S": shared_with.to_string()},
        "permission": {"S": permission},
        "shared_by": {"S": shared_by.to_string()},
        "created_at": {"S": created_at},
    })
}

pub fn get_item_response(item: Value) -> Value {
    json!({ "Item": item })
}

pub fn scan_response(items: Vec<Value>) -> Value {
    json!({ "Items": items, "Count": items.len(), "ScannedCount": items.len() })
}

// -- Redis --

/// Starts a minimal in-process RESP server on loopback that answers `EXISTS`
/// with 1 for the given keys and 0 otherwise, and returns a connection to it.
pub async fn fake_redis(set_keys: &[&str]) -> redis::aio::ConnectionManager {
    use tokio::io::{AsyncBufReadExt, AsyncReadExt, AsyncWriteExt, BufReader};

    let keys: Vec<String> = set_keys.iter().map(|k| k.to_string()).collect();
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        while let Ok((socket, _)) = listener.accept().await {
            let keys = keys.clone();
            tokio::spawn(async move {
                let (read, mut write) = socket.into_split();
                let mut read = BufReader::new(read);
                let mut line = String::new();
                loop {
                    line.clear();
                    if read.read_line(&mut line).await.unwrap_or(0) == 0 {
                        return;
                    }
                    let argc: usize = line.trim_start_matches('*').trim().parse().unwrap_or(0);
                    let mut args = Vec::with_capacity(argc);
                    for _ in 0..argc {
                        line.clear();
                        read.read_line(&mut line).await.unwrap();
                        let len: usize = line.trim_start_matches('$').trim().parse().unwrap();
                        let mut buf = vec![0; len + 2];
                        read.read_exact(&mut buf).await.unwrap();
                        args.push(String::from_utf8_lossy(&buf[..len]).to_string());
                    }
                    let reply = match args.first().map(|c| c.to_uppercase()).as_deref() {
                        Some("EXISTS") => {
                            let n = args[1..].iter().filter(|a| keys.contains(a)).count();
                            format!(":{n}\r\n")
                        }
                        _ => "+OK\r\n".to_string(),
                    };
                    if write.write_all(reply.as_bytes()).await.is_err() {
                        return;
                    }
                }
            });
        }
    });
    let client = redis::Client::open(format!("redis://{addr}")).unwrap();
    redis::aio::ConnectionManager::new(client).await.unwrap()
}
