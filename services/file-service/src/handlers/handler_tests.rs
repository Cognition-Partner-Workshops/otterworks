use super::*;
use actix_web::http::{header, Method, StatusCode};
use actix_web::{test, App, HttpServer};
use aws_sdk_dynamodb::config::{Credentials, Region};
use serde_json::{json, Value};
use std::collections::VecDeque;
use std::net::TcpListener;
use std::sync::Mutex;
use std::time::Duration;
use tokio::io::AsyncWriteExt;

const OWNER: &str = "00000000-0000-4000-8000-000000000001";
const OTHER_USER: &str = "00000000-0000-4000-8000-000000000002";
const FILE: &str = "00000000-0000-4000-8000-000000000003";
const OTHER_FILE: &str = "00000000-0000-4000-8000-000000000004";
const FOLDER: &str = "00000000-0000-4000-8000-000000000005";
const SHARE: &str = "00000000-0000-4000-8000-000000000006";
const TIMESTAMP: &str = "2026-01-01T12:00:00Z";

struct CloudRequest {
    method: Method,
    path: String,
    target: Option<String>,
    content_type: Option<String>,
    body: web::Bytes,
}

impl CloudRequest {
    fn dynamo_body(&self, operation: &str, table: &str) -> Value {
        assert_eq!(
            self.target.as_deref(),
            Some(format!("DynamoDB_20120810.{operation}").as_str())
        );
        let body: Value = serde_json::from_slice(&self.body).unwrap();
        assert_eq!(body["TableName"], table);
        body
    }
}

type CloudResponse = (StatusCode, &'static str, String);

fn dynamo(body: Value) -> CloudResponse {
    (
        StatusCode::OK,
        "application/x-amz-json-1.0",
        body.to_string(),
    )
}

struct CloudStub {
    endpoint: String,
    server: actix_web::dev::ServerHandle,
    requests: web::Data<Mutex<Vec<CloudRequest>>>,
}

impl CloudStub {
    fn start(responses: impl IntoIterator<Item = CloudResponse>) -> Self {
        let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
        let endpoint = format!("http://{}", listener.local_addr().unwrap());
        let requests = web::Data::new(Mutex::new(Vec::new()));
        let responses = web::Data::new(Mutex::new(responses.into_iter().collect::<VecDeque<_>>()));
        let server = HttpServer::new({
            let requests = requests.clone();
            let responses = responses.clone();
            move || {
                App::new()
                    .app_data(requests.clone())
                    .app_data(responses.clone())
                    .default_service(web::to(
                        |req: HttpRequest,
                         body: web::Bytes,
                         requests: web::Data<Mutex<Vec<CloudRequest>>>,
                         responses: web::Data<Mutex<VecDeque<CloudResponse>>>| async move {
                            let header = |name| {
                                req.headers().get(name).map(|v| v.to_str().unwrap().to_owned())
                            };
                            requests.lock().unwrap().push(CloudRequest {
                                method: req.method().clone(),
                                path: req.path().to_owned(),
                                target: header("x-amz-target"),
                                content_type: header("content-type"),
                                body,
                            });
                            match responses.lock().unwrap().pop_front() {
                                Some((status, content_type, body)) => HttpResponse::build(status)
                                    .content_type(content_type)
                                    .body(body),
                                None => HttpResponse::InternalServerError()
                                    .body("unexpected cloud request"),
                            }
                        },
                    ))
            }
        })
        .workers(1)
        .disable_signals()
        .listen(listener)
        .unwrap()
        .run();
        let handle = server.handle();
        actix_rt::spawn(server);
        Self {
            endpoint,
            server: handle,
            requests,
        }
    }

    fn metadata(&self) -> web::Data<MetadataClient> {
        let config = aws_sdk_dynamodb::config::Builder::new()
            .behavior_version_latest()
            .region(Region::new("us-east-1"))
            .credentials_provider(Credentials::new("test", "test", None, None, "test"))
            .retry_config(aws_sdk_dynamodb::config::retry::RetryConfig::disabled())
            .endpoint_url(&self.endpoint)
            .build();
        web::Data::new(MetadataClient {
            client: aws_sdk_dynamodb::Client::from_conf(config),
            files_table: "files".into(),
            folders_table: "folders".into(),
            versions_table: "versions".into(),
            shares_table: "shares".into(),
        })
    }

    fn storage(&self) -> web::Data<S3Client> {
        let config = aws_sdk_s3::config::Builder::new()
            .behavior_version_latest()
            .region(Region::new("us-east-1"))
            .credentials_provider(Credentials::new("test", "test", None, None, "test"))
            .retry_config(aws_sdk_s3::config::retry::RetryConfig::disabled())
            .endpoint_url(&self.endpoint)
            .force_path_style(true)
            .request_checksum_calculation(
                aws_sdk_s3::config::RequestChecksumCalculation::WhenRequired,
            )
            .build();
        web::Data::new(S3Client {
            client: aws_sdk_s3::Client::from_conf(config),
            bucket: "test-bucket".into(),
        })
    }

    fn aws_config(&self) -> crate::config::AwsConfig {
        crate::config::AwsConfig {
            region: "us-east-1".into(),
            endpoint_url: Some(self.endpoint.clone()),
            s3_bucket: "test-bucket".into(),
            dynamodb_table: "files".into(),
            dynamodb_folders_table: "folders".into(),
            dynamodb_versions_table: "versions".into(),
            dynamodb_shares_table: "shares".into(),
        }
    }

    async fn finish(self) -> Vec<CloudRequest> {
        self.server.stop(false).await;
        std::mem::take(&mut *self.requests.lock().unwrap())
    }
}

async fn redis_without_chaos() -> web::Data<redis::aio::ConnectionManager> {
    let listener = tokio::net::TcpListener::bind(("127.0.0.1", 0))
        .await
        .unwrap();
    let client =
        redis::Client::open(format!("redis://{}", listener.local_addr().unwrap())).unwrap();
    actix_rt::spawn(async move {
        let (mut stream, _) = listener.accept().await.unwrap();
        let mut decoder = Default::default();
        while let Ok(command) = redis::parse_redis_value_async(&mut decoder, &mut stream).await {
            let args: Vec<String> = redis::from_redis_value(&command).unwrap();
            let reply: &[u8] = match args.first().map(String::as_str) {
                Some("CLIENT") => b"+OK\r\n",
                Some("PING") => b"+PONG\r\n",
                Some("EXISTS")
                    if args.get(1).map(String::as_str)
                        == Some("chaos:file-service:upload_s3_error") =>
                {
                    b":0\r\n"
                }
                _ => b"-ERR unexpected test command\r\n",
            };
            stream.write_all(reply).await.unwrap();
        }
    });
    let connection = tokio::time::timeout(
        Duration::from_secs(10),
        redis::aio::ConnectionManager::new(client),
    )
    .await
    .unwrap()
    .unwrap();
    web::Data::new(connection)
}

fn upload_request(file: Option<&str>, fields: &[(&str, &str)]) -> test::TestRequest {
    let mut body = String::new();
    for (name, value) in fields {
        body.push_str(&format!(
            "--upload\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n"
        ));
    }
    if let Some(data) = file {
        body.push_str(&format!(
            "--upload\r\nContent-Disposition: form-data; name=\"file\"; filename=\"notes.txt\"\r\nContent-Type: text/plain\r\n\r\n{data}\r\n"
        ));
    }
    body.push_str("--upload--\r\n");
    test::TestRequest::post()
        .uri("/api/v1/files/upload")
        .insert_header((header::CONTENT_TYPE, "multipart/form-data; boundary=upload"))
        .set_payload(body)
}

fn upload_config(cloud: &CloudStub, max_upload_bytes: u64) -> web::Data<AppConfig> {
    web::Data::new(AppConfig {
        server: crate::config::ServerConfig {
            port: 0,
            max_upload_bytes,
        },
        aws: cloud.aws_config(),
        sns: crate::config::SnsConfig { topic_arn: None },
    })
}

async fn upload_route(cloud: &CloudStub, max_upload_bytes: u64) -> actix_web::Scope {
    web::scope("/api/v1/files")
        .app_data(cloud.metadata())
        .app_data(cloud.storage())
        .app_data(web::Data::new(EventPublisher::disabled_for_tests()))
        .app_data(upload_config(cloud, max_upload_bytes))
        .app_data(redis_without_chaos().await)
        .route("/upload", web::post().to(upload_file))
}

#[actix_rt::test]
async fn upload_at_exact_limit_persists_content_metadata_and_first_version_for_signed_in_owner() {
    let cloud = CloudStub::start([
        (StatusCode::OK, "application/xml", String::new()),
        dynamo(json!({})),
        dynamo(json!({})),
    ]);
    let app = test::init_service(App::new().service(upload_route(&cloud, 5).await)).await;
    let request = upload_request(
        Some("café"),
        &[("owner_id", OTHER_USER), ("folder_id", FOLDER)],
    )
    .insert_header(("X-User-ID", OWNER))
    .to_request();
    let response = test::call_service(&app, request).await;
    assert_eq!(response.status(), StatusCode::CREATED);
    let body: Value = test::read_body_json(response).await;
    let file: FileMetadata = serde_json::from_value(body["file"].clone()).unwrap();
    assert_eq!(file.owner_id.to_string(), OWNER);
    assert_eq!(
        file.folder_id.map(|id| id.to_string()).as_deref(),
        Some(FOLDER)
    );
    assert_eq!(file.name, "notes.txt");
    assert_eq!(file.mime_type, "text/plain");
    assert_eq!(file.size_bytes, 5);
    assert_eq!(file.version, 1);
    assert!(!file.is_trashed);
    assert_eq!(file.s3_key, format!("files/{OWNER}/{}", file.id));

    let requests = cloud.finish().await;
    assert_eq!(requests.len(), 3);
    assert_eq!(requests[0].method, Method::PUT);
    assert_eq!(requests[0].path, format!("/test-bucket/{}", file.s3_key));
    assert_eq!(requests[0].content_type.as_deref(), Some("text/plain"));
    assert_eq!(requests[0].body.as_ref(), "café".as_bytes());
    let metadata = &requests[1].dynamo_body("PutItem", "files")["Item"];
    assert_eq!(metadata["id"]["S"], file.id.to_string());
    assert_eq!(metadata["owner_id"]["S"], OWNER);
    assert_eq!(metadata["folder_id"]["S"], FOLDER);
    assert_eq!(metadata["size_bytes"]["N"], "5");
    assert_eq!(metadata["s3_key"]["S"], file.s3_key);
    let version = &requests[2].dynamo_body("PutItem", "versions")["Item"];
    assert_eq!(version["file_id"]["S"], file.id.to_string());
    assert_eq!(version["version"]["N"], "1");
    assert_eq!(version["created_by"]["S"], OWNER);
    assert_eq!(version["size_bytes"]["N"], "5");
    assert_eq!(version["s3_key"]["S"], file.s3_key);
}

#[actix_rt::test]
async fn upload_over_byte_limit_returns_413_without_cloud_writes() {
    let cloud = CloudStub::start([]);
    let app = test::init_service(App::new().service(upload_route(&cloud, 5).await)).await;
    let request = upload_request(Some("café!"), &[("owner_id", OWNER)]).to_request();
    let response = test::call_service(&app, request).await;
    assert_eq!(response.status(), StatusCode::PAYLOAD_TOO_LARGE);
    let body: Value = test::read_body_json(response).await;
    assert_eq!(body["error"], "file_too_large");
    assert_eq!(body["message"], "File too large: max 5 bytes, got 6 bytes");
    assert!(cloud.finish().await.is_empty());
}

#[actix_rt::test]
async fn upload_rejects_missing_file_and_malformed_multipart_ids_without_cloud_writes() {
    let cloud = CloudStub::start([]);
    let app = test::init_service(App::new().service(upload_route(&cloud, 16).await)).await;
    for (request, message) in [
        (
            upload_request(None, &[("owner_id", OWNER)]),
            "file field is required",
        ),
        (upload_request(Some("hi"), &[]), "owner_id is required"),
        (
            upload_request(Some("hi"), &[("owner_id", "bad")]),
            "invalid owner_id",
        ),
        (
            upload_request(Some("hi"), &[("owner_id", OWNER), ("folder_id", "bad")]),
            "invalid folder_id",
        ),
    ] {
        let response = test::call_service(&app, request.to_request()).await;
        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
        let body: Value = test::read_body_json(response).await;
        assert_eq!(body["error"], "bad_request");
        assert!(
            body["message"].as_str().unwrap().contains(message),
            "{body}"
        );
    }
    assert!(cloud.finish().await.is_empty());
}

fn file_item(id: &str, trashed: bool) -> Value {
    json!({
        "id": {"S": id},
        "owner_id": {"S": OWNER},
        "s3_key": {"S": format!("files/{OWNER}/{id}")},
        "name": {"S": "notes.txt"},
        "mime_type": {"S": "text/plain"},
        "size_bytes": {"N": "7"},
        "version": {"N": "1"},
        "is_trashed": {"BOOL": trashed},
        "created_at": {"S": TIMESTAMP},
        "updated_at": {"S": TIMESTAMP},
    })
}

fn share_item(id: &str, file: &str) -> Value {
    json!({
        "id": {"S": id},
        "file_id": {"S": file},
        "shared_with": {"S": OTHER_USER},
        "shared_by": {"S": OWNER},
        "permission": {"S": "viewer"},
        "created_at": {"S": TIMESTAMP},
    })
}

#[actix_rt::test]
async fn file_listing_scopes_to_signed_in_owner_and_paginates_across_scan_pages() {
    let resume_key = json!({"id": {"S": FILE}});
    let cloud = CloudStub::start([
        dynamo(json!({"Items": [file_item(FILE, false)], "LastEvaluatedKey": resume_key})),
        dynamo(json!({"Items": [file_item(OTHER_FILE, false)]})),
    ]);
    let app = test::init_service(
        App::new()
            .app_data(cloud.metadata())
            .route("/api/v1/files", web::get().to(list_files)),
    )
    .await;
    let request = test::TestRequest::get()
        .uri(&format!(
            "/api/v1/files?owner_id={OTHER_USER}&folder_id={FOLDER}&page=2&page_size=1"
        ))
        .insert_header(("X-User-ID", OWNER))
        .to_request();
    let response = test::call_service(&app, request).await;
    assert_eq!(response.status(), StatusCode::OK);
    let body: Value = test::read_body_json(response).await;
    assert_eq!(body["total"], 2);
    assert_eq!(body["page"], 2);
    assert_eq!(body["page_size"], 1);
    assert_eq!(body["files"].as_array().unwrap().len(), 1);
    assert_eq!(body["files"][0]["id"], OTHER_FILE);

    let requests = cloud.finish().await;
    assert_eq!(requests.len(), 2);
    for request in &requests {
        let scan = request.dynamo_body("Scan", "files");
        assert_eq!(
            scan["FilterExpression"],
            "folder_id = :folder_id AND owner_id = :owner_id AND is_trashed = :trashed"
        );
        assert_eq!(
            scan["ExpressionAttributeValues"],
            json!({
                ":folder_id": {"S": FOLDER},
                ":owner_id": {"S": OWNER},
                ":trashed": {"BOOL": false},
            })
        );
    }
    assert_eq!(
        requests[1].dynamo_body("Scan", "files")["ExclusiveStartKey"],
        resume_key
    );
}

#[actix_rt::test]
async fn file_listing_bounds_client_page_parameters_and_allows_internal_owner_filter() {
    let cloud = CloudStub::start([dynamo(json!({"Items": [file_item(FILE, true)]}))]);
    let app = test::init_service(
        App::new()
            .app_data(cloud.metadata())
            .route("/api/v1/files", web::get().to(list_files)),
    )
    .await;
    let request = test::TestRequest::get()
        .uri(&format!(
            "/api/v1/files?owner_id={OWNER}&include_trashed=true&page=0&page_size=500"
        ))
        .to_request();
    let response = test::call_service(&app, request).await;
    assert_eq!(response.status(), StatusCode::OK);
    let body: Value = test::read_body_json(response).await;
    assert_eq!(body["page"], 1);
    assert_eq!(body["page_size"], 100);
    assert_eq!(body["files"][0]["is_trashed"], true);
    let requests = cloud.finish().await;
    assert_eq!(requests.len(), 1);
    let scan = requests[0].dynamo_body("Scan", "files");
    assert_eq!(scan["FilterExpression"], "owner_id = :owner_id");
    assert_eq!(scan["ExpressionAttributeValues"][":owner_id"]["S"], OWNER);
}

#[actix_rt::test]
async fn shared_listing_requires_identity_before_querying_shares() {
    let cloud = CloudStub::start([]);
    let app = test::init_service(
        App::new()
            .app_data(cloud.metadata())
            .route("/api/v1/files/shared", web::get().to(list_shared_files)),
    )
    .await;
    for request in [
        test::TestRequest::get(),
        test::TestRequest::get().insert_header(("X-User-ID", "not-a-uuid")),
    ] {
        let response =
            test::call_service(&app, request.uri("/api/v1/files/shared").to_request()).await;
        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
        let body: Value = test::read_body_json(response).await;
        assert_eq!(body["error"], "bad_request");
        assert_eq!(body["message"], "Bad request: missing X-User-ID header");
    }
    assert!(cloud.finish().await.is_empty());
}

#[actix_rt::test]
async fn shared_listing_hides_trashed_and_missing_files_and_deduplicates_shares() {
    let cloud = CloudStub::start([
        dynamo(json!({"Items": [
            share_item(SHARE, FILE),
            share_item("00000000-0000-4000-8000-000000000007", FILE),
            share_item("00000000-0000-4000-8000-000000000008", OTHER_FILE),
            share_item("00000000-0000-4000-8000-000000000009", FOLDER),
        ]})),
        dynamo(json!({"Item": file_item(FILE, false)})),
        dynamo(json!({"Item": file_item(OTHER_FILE, true)})),
        dynamo(json!({})),
    ]);
    let app = test::init_service(
        App::new()
            .app_data(cloud.metadata())
            .route("/api/v1/files/shared", web::get().to(list_shared_files)),
    )
    .await;
    let request = test::TestRequest::get()
        .uri("/api/v1/files/shared")
        .insert_header(("X-User-ID", OTHER_USER))
        .to_request();
    let response = test::call_service(&app, request).await;
    assert_eq!(response.status(), StatusCode::OK);
    let body: Value = test::read_body_json(response).await;
    assert_eq!(body["total"], 1);
    assert_eq!(body["files"].as_array().unwrap().len(), 1);
    assert_eq!(body["files"][0]["id"], FILE);
    let requests = cloud.finish().await;
    assert_eq!(requests.len(), 4);
    let scan = requests[0].dynamo_body("Scan", "shares");
    assert_eq!(scan["FilterExpression"], "shared_with = :uid");
    assert_eq!(scan["ExpressionAttributeValues"][":uid"]["S"], OTHER_USER);
    for (request, id) in requests[1..].iter().zip([FILE, OTHER_FILE, FOLDER]) {
        assert_eq!(
            request.dynamo_body("GetItem", "files")["Key"]["id"]["S"],
            id
        );
    }
}

#[actix_rt::test]
async fn download_returns_a_signed_url_for_the_stored_object_with_one_hour_expiry() {
    let cloud = CloudStub::start([dynamo(json!({"Item": file_item(FILE, false)}))]);
    let app = test::init_service(
        App::new()
            .app_data(cloud.metadata())
            .app_data(cloud.storage())
            .route("/api/v1/files/{id}/download", web::get().to(download_file)),
    )
    .await;
    let request = test::TestRequest::get()
        .uri(&format!("/api/v1/files/{FILE}/download"))
        .to_request();
    let response = test::call_service(&app, request).await;
    assert_eq!(response.status(), StatusCode::OK);
    let body: Value = test::read_body_json(response).await;
    assert_eq!(body["expires_in_secs"], 3600);
    let url = body["url"].as_str().unwrap();
    let (location, query) = url.split_once('?').unwrap();
    assert_eq!(
        location,
        format!("{}/test-bucket/files/{OWNER}/{FILE}", cloud.endpoint)
    );
    assert!(query.split('&').any(|p| p == "X-Amz-Expires=3600"));
    assert!(query.split('&').any(|p| p.starts_with("X-Amz-Signature=")));
    let requests = cloud.finish().await;
    assert_eq!(requests.len(), 1, "signing should not download file bytes");
    assert_eq!(
        requests[0].dynamo_body("GetItem", "files")["Key"]["id"]["S"],
        FILE
    );
}

#[actix_rt::test]
async fn file_lookup_distinguishes_bad_id_missing_file_and_metadata_outage() {
    let cloud = CloudStub::start([
        dynamo(json!({})),
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            "application/x-amz-json-1.0",
            json!({"__type": "InternalServerError", "message": "unavailable"}).to_string(),
        ),
    ]);
    let app = test::init_service(
        App::new()
            .app_data(cloud.metadata())
            .route("/api/v1/files/{id}", web::get().to(get_file_metadata)),
    )
    .await;
    for (id, expected_status, expected_error) in [
        ("invalid-id", StatusCode::BAD_REQUEST, "bad_request"),
        (FILE, StatusCode::NOT_FOUND, "file_not_found"),
        (
            OTHER_FILE,
            StatusCode::INTERNAL_SERVER_ERROR,
            "metadata_error",
        ),
    ] {
        let request = test::TestRequest::get()
            .uri(&format!("/api/v1/files/{id}"))
            .to_request();
        let response = test::call_service(&app, request).await;
        assert_eq!(response.status(), expected_status);
        let body: Value = test::read_body_json(response).await;
        assert_eq!(body["error"], expected_error);
    }
    let requests = cloud.finish().await;
    assert_eq!(requests.len(), 2);
    for (request, id) in requests.iter().zip([FILE, OTHER_FILE]) {
        assert_eq!(
            request.dynamo_body("GetItem", "files")["Key"]["id"]["S"],
            id
        );
    }
}

#[actix_rt::test]
async fn permanent_delete_removes_the_metadata_and_stored_object() {
    let database = CloudStub::start([
        dynamo(json!({"Item": file_item(FILE, true)})),
        dynamo(json!({})),
    ]);
    let storage = CloudStub::start([(StatusCode::NO_CONTENT, "application/xml", String::new())]);
    let app = test::init_service(
        App::new()
            .app_data(database.metadata())
            .app_data(storage.storage())
            .app_data(web::Data::new(EventPublisher::disabled_for_tests()))
            .route("/api/v1/files/{id}", web::delete().to(delete_file)),
    )
    .await;
    let request = test::TestRequest::delete()
        .uri(&format!("/api/v1/files/{FILE}"))
        .to_request();
    let response = test::call_service(&app, request).await;
    assert_eq!(response.status(), StatusCode::NO_CONTENT);
    assert!(test::read_body(response).await.is_empty());

    let requests = database.finish().await;
    assert_eq!(requests.len(), 2);
    assert_eq!(
        requests[0].dynamo_body("GetItem", "files")["Key"]["id"]["S"],
        FILE
    );
    assert_eq!(
        requests[1].dynamo_body("DeleteItem", "files")["Key"]["id"]["S"],
        FILE
    );
    let requests = storage.finish().await;
    assert_eq!(requests.len(), 1);
    assert_eq!(requests[0].method, Method::DELETE);
    assert_eq!(
        requests[0].path,
        format!("/test-bucket/files/{OWNER}/{FILE}")
    );
}

#[actix_rt::test]
#[ignore = "BUG: permanent delete removes DynamoDB metadata before S3 deletion succeeds, preventing retry"]
async fn failed_permanent_delete_preserves_metadata_for_retry() {
    let database = CloudStub::start([
        dynamo(json!({"Item": file_item(FILE, true)})),
        dynamo(json!({})),
    ]);
    let storage = CloudStub::start([(
        StatusCode::INTERNAL_SERVER_ERROR,
        "application/xml",
        "<Error><Code>InternalError</Code><Message>unavailable</Message></Error>".into(),
    )]);
    let app = test::init_service(
        App::new()
            .app_data(database.metadata())
            .app_data(storage.storage())
            .app_data(web::Data::new(EventPublisher::disabled_for_tests()))
            .route("/api/v1/files/{id}", web::delete().to(delete_file)),
    )
    .await;
    let request = test::TestRequest::delete()
        .uri(&format!("/api/v1/files/{FILE}"))
        .to_request();
    let response = test::call_service(&app, request).await;
    assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
    let body: Value = test::read_body_json(response).await;
    assert_eq!(body["error"], "storage_error");

    let storage_requests = storage.finish().await;
    assert_eq!(storage_requests.len(), 1);
    assert_eq!(storage_requests[0].method, Method::DELETE);
    assert_eq!(
        storage_requests[0].path,
        format!("/test-bucket/files/{OWNER}/{FILE}")
    );
    let database_requests = database.finish().await;
    assert_eq!(
        database_requests[0].dynamo_body("GetItem", "files")["Key"]["id"]["S"],
        FILE
    );
    assert_eq!(
        database_requests.len(),
        1,
        "metadata must remain when the object cannot be deleted"
    );
}

#[actix_rt::test]
async fn move_sets_folder_and_clears_it_when_moving_to_root() {
    let mut nested = file_item(FILE, false);
    nested["folder_id"] = json!({"S": FOLDER});
    let cloud = CloudStub::start([
        dynamo(json!({})),
        dynamo(json!({"Item": nested})),
        dynamo(json!({})),
        dynamo(json!({"Item": file_item(FILE, false)})),
    ]);
    let app = test::init_service(
        App::new()
            .app_data(cloud.metadata())
            .app_data(web::Data::new(EventPublisher::disabled_for_tests()))
            .route("/api/v1/files/{id}/move", web::put().to(move_file)),
    )
    .await;
    for folder in [json!(FOLDER), Value::Null] {
        let request = test::TestRequest::put()
            .uri(&format!("/api/v1/files/{FILE}/move"))
            .set_json(json!({"folder_id": folder}))
            .to_request();
        let response = test::call_service(&app, request).await;
        assert_eq!(response.status(), StatusCode::OK);
        let body: Value = test::read_body_json(response).await;
        assert_eq!(body["id"], FILE);
        assert_eq!(body["folder_id"], folder);
    }
    let requests = cloud.finish().await;
    assert_eq!(requests.len(), 4);
    let into_folder = requests[0].dynamo_body("UpdateItem", "files");
    let into_root = requests[2].dynamo_body("UpdateItem", "files");
    for update in [&into_folder, &into_root] {
        assert_eq!(update["Key"]["id"]["S"], FILE);
        assert_eq!(update["ConditionExpression"], "attribute_exists(id)");
    }
    assert_eq!(
        into_folder["UpdateExpression"],
        "SET folder_id = :f, updated_at = :u"
    );
    assert_eq!(into_folder["ExpressionAttributeValues"][":f"]["S"], FOLDER);
    assert_eq!(
        into_root["UpdateExpression"],
        "SET updated_at = :u REMOVE folder_id"
    );
    for request in [&requests[1], &requests[3]] {
        assert_eq!(
            request.dynamo_body("GetItem", "files")["Key"]["id"]["S"],
            FILE
        );
    }
}

#[actix_rt::test]
async fn moving_a_missing_file_does_not_create_it() {
    let cloud = CloudStub::start([(
        StatusCode::BAD_REQUEST,
        "application/x-amz-json-1.0",
        json!({"__type": "ConditionalCheckFailedException", "message": "missing item"}).to_string(),
    )]);
    let app = test::init_service(
        App::new()
            .app_data(cloud.metadata())
            .app_data(web::Data::new(EventPublisher::disabled_for_tests()))
            .route("/api/v1/files/{id}/move", web::put().to(move_file)),
    )
    .await;
    let request = test::TestRequest::put()
        .uri(&format!("/api/v1/files/{FILE}/move"))
        .set_json(json!({"folder_id": FOLDER}))
        .to_request();
    let response = test::call_service(&app, request).await;
    assert_eq!(response.status(), StatusCode::NOT_FOUND);
    let body: Value = test::read_body_json(response).await;
    assert_eq!(body["error"], "file_not_found");
    let requests = cloud.finish().await;
    assert_eq!(requests.len(), 1);
    assert_eq!(
        requests[0].dynamo_body("UpdateItem", "files")["ConditionExpression"],
        "attribute_exists(id)"
    );
}

#[actix_rt::test]
async fn sharing_creates_a_new_recipient_record() {
    let cloud = CloudStub::start([
        dynamo(json!({"Item": file_item(FILE, false)})),
        dynamo(json!({"Items": []})),
        dynamo(json!({})),
    ]);
    let app = test::init_service(
        App::new()
            .app_data(cloud.metadata())
            .app_data(web::Data::new(EventPublisher::disabled_for_tests()))
            .route("/api/v1/files/{id}/share", web::post().to(share_file)),
    )
    .await;
    let request = test::TestRequest::post()
        .uri(&format!("/api/v1/files/{FILE}/share"))
        .set_json(json!({"shared_by": OWNER, "shared_with": OTHER_USER, "permission": "viewer"}))
        .to_request();
    let response = test::call_service(&app, request).await;
    assert_eq!(response.status(), StatusCode::CREATED);
    let body: Value = test::read_body_json(response).await;
    let share: FileShare = serde_json::from_value(body["share"].clone()).unwrap();
    assert_eq!(share.file_id.to_string(), FILE);
    assert_eq!(share.shared_with.to_string(), OTHER_USER);
    assert_eq!(share.shared_by.to_string(), OWNER);
    assert_eq!(share.permission, crate::models::SharePermission::Viewer);
    let requests = cloud.finish().await;
    assert_eq!(requests.len(), 3);
    let initial = &requests[2].dynamo_body("PutItem", "shares")["Item"];
    assert_eq!(initial["id"]["S"], share.id.to_string());
    assert_eq!(initial["file_id"]["S"], FILE);
    assert_eq!(initial["shared_with"]["S"], OTHER_USER);
    assert_eq!(initial["permission"]["S"], "viewer");
}

#[actix_rt::test]
async fn sharing_again_reuses_the_existing_record_and_only_writes_changed_permission() {
    let cloud = CloudStub::start([
        dynamo(json!({"Item": file_item(FILE, false)})),
        dynamo(json!({"Items": [share_item(SHARE, FILE)]})),
        dynamo(json!({"Item": file_item(FILE, false)})),
        dynamo(json!({"Items": [share_item(SHARE, FILE)]})),
        dynamo(json!({})),
    ]);
    let app = test::init_service(
        App::new()
            .app_data(cloud.metadata())
            .app_data(web::Data::new(EventPublisher::disabled_for_tests()))
            .route("/api/v1/files/{id}/share", web::post().to(share_file)),
    )
    .await;
    for permission in ["viewer", "editor"] {
        let request = test::TestRequest::post()
            .uri(&format!("/api/v1/files/{FILE}/share"))
            .set_json(
                json!({"shared_by": OWNER, "shared_with": OTHER_USER, "permission": permission}),
            )
            .to_request();
        let response = test::call_service(&app, request).await;
        assert_eq!(response.status(), StatusCode::OK);
        let body: Value = test::read_body_json(response).await;
        let share: FileShare = serde_json::from_value(body["share"].clone()).unwrap();
        assert_eq!(share.file_id.to_string(), FILE);
        assert_eq!(share.shared_with.to_string(), OTHER_USER);
        assert_eq!(share.permission.to_string(), permission);
        assert_eq!(share.id.to_string(), SHARE);
        assert_eq!(share.created_at.to_rfc3339(), "2026-01-01T12:00:00+00:00");
    }
    let requests = cloud.finish().await;
    assert_eq!(requests.len(), 5);
    for index in [1, 3] {
        let request = requests[index].dynamo_body("Scan", "shares");
        assert_eq!(
            request["FilterExpression"],
            "file_id = :fid AND shared_with = :uid"
        );
        assert_eq!(request["ExpressionAttributeValues"][":fid"]["S"], FILE);
        assert_eq!(
            request["ExpressionAttributeValues"][":uid"]["S"],
            OTHER_USER
        );
    }
    let updated = requests[4].dynamo_body("PutItem", "shares");
    assert_eq!(updated["Item"]["id"]["S"], SHARE);
    assert_eq!(updated["Item"]["permission"]["S"], "editor");
}

#[actix_rt::test]
async fn revoke_share_deletes_only_the_recipient_record_and_reports_missing_share() {
    let cloud = CloudStub::start([
        dynamo(json!({"Item": file_item(FILE, false)})),
        dynamo(json!({"Items": [share_item(SHARE, FILE)]})),
        dynamo(json!({})),
        dynamo(json!({"Item": file_item(FILE, false)})),
        dynamo(json!({"Items": []})),
    ]);
    let app = test::init_service(App::new().app_data(cloud.metadata()).route(
        "/api/v1/files/{id}/share/{user}",
        web::delete().to(remove_share),
    ))
    .await;
    for expected_status in [StatusCode::NO_CONTENT, StatusCode::NOT_FOUND] {
        let request = test::TestRequest::delete()
            .uri(&format!("/api/v1/files/{FILE}/share/{OTHER_USER}"))
            .to_request();
        let response = test::call_service(&app, request).await;
        assert_eq!(response.status(), expected_status);
        if expected_status == StatusCode::NOT_FOUND {
            let body: Value = test::read_body_json(response).await;
            assert_eq!(body["error"], "share_not_found");
        }
    }
    let requests = cloud.finish().await;
    assert_eq!(
        requests.len(),
        5,
        "no second delete after the share is gone"
    );
    assert_eq!(
        requests[2].dynamo_body("DeleteItem", "shares")["Key"]["id"]["S"],
        SHARE
    );
}

#[actix_rt::test]
async fn folder_listing_distinguishes_root_and_nested_folders_for_the_signed_in_owner() {
    let mut folder = json!({
        "id": {"S": FOLDER}, "name": {"S": "Drafts"}, "owner_id": {"S": OWNER},
        "created_at": {"S": TIMESTAMP}, "updated_at": {"S": TIMESTAMP},
    });
    let root = dynamo(json!({"Items": [folder]}));
    folder["id"]["S"] = json!(OTHER_FILE);
    folder["parent_id"] = json!({"S": FOLDER});
    let cloud = CloudStub::start([root, dynamo(json!({"Items": [folder]}))]);
    let app = test::init_service(
        App::new()
            .app_data(cloud.metadata())
            .route("/api/v1/folders", web::get().to(list_folders)),
    )
    .await;
    for (parent_filter, expected_id, expected_parent) in [
        (String::new(), FOLDER, Value::Null),
        (format!("&parent_id={FOLDER}"), OTHER_FILE, json!(FOLDER)),
    ] {
        let request = test::TestRequest::get()
            .uri(&format!(
                "/api/v1/folders?owner_id={OTHER_USER}{parent_filter}"
            ))
            .insert_header(("X-User-ID", OWNER))
            .to_request();
        let response = test::call_service(&app, request).await;
        assert_eq!(response.status(), StatusCode::OK);
        let body: Value = test::read_body_json(response).await;
        assert_eq!(body["folders"].as_array().unwrap().len(), 1);
        assert_eq!(body["folders"][0]["id"], expected_id);
        assert_eq!(body["folders"][0]["parent_id"], expected_parent);
    }
    let requests = cloud.finish().await;
    assert_eq!(requests.len(), 2);
    let root = requests[0].dynamo_body("Scan", "folders");
    let nested = requests[1].dynamo_body("Scan", "folders");
    assert_eq!(
        root["FilterExpression"],
        "attribute_not_exists(parent_id) AND owner_id = :owner_id"
    );
    assert_eq!(
        nested["FilterExpression"],
        "parent_id = :parent_id AND owner_id = :owner_id"
    );
    assert_eq!(
        nested["ExpressionAttributeValues"][":parent_id"]["S"],
        FOLDER
    );
    for request in [root, nested] {
        assert_eq!(
            request["ExpressionAttributeValues"][":owner_id"]["S"],
            OWNER
        );
    }
}

#[actix_rt::test]
async fn trash_lists_newest_first_and_restore_clears_the_trashed_flag() {
    let mut newer = file_item(OTHER_FILE, true);
    newer["updated_at"]["S"] = json!("2026-01-02T12:00:00Z");
    let cloud = CloudStub::start([
        dynamo(json!({"Items": [file_item(FILE, true), newer]})),
        dynamo(json!({})),
        dynamo(json!({"Item": file_item(OTHER_FILE, false)})),
    ]);
    let app = test::init_service(
        App::new()
            .app_data(cloud.metadata())
            .app_data(web::Data::new(EventPublisher::disabled_for_tests()))
            .route("/api/v1/files/trash", web::get().to(list_trashed))
            .route("/api/v1/files/{id}/restore", web::post().to(restore_file)),
    )
    .await;
    let request = test::TestRequest::get()
        .uri("/api/v1/files/trash?page_size=1")
        .insert_header(("X-User-ID", OWNER))
        .to_request();
    let response = test::call_service(&app, request).await;
    assert_eq!(response.status(), StatusCode::OK);
    let body: Value = test::read_body_json(response).await;
    assert_eq!(body["total"], 2);
    assert_eq!(body["files"].as_array().unwrap().len(), 1);
    assert_eq!(body["files"][0]["id"], OTHER_FILE);

    let request = test::TestRequest::post()
        .uri(&format!("/api/v1/files/{OTHER_FILE}/restore"))
        .to_request();
    let response = test::call_service(&app, request).await;
    assert_eq!(response.status(), StatusCode::OK);
    let body: Value = test::read_body_json(response).await;
    assert_eq!(body["id"], OTHER_FILE);
    assert_eq!(body["is_trashed"], false);

    let requests = cloud.finish().await;
    assert_eq!(requests.len(), 3);
    let scan = requests[0].dynamo_body("Scan", "files");
    assert_eq!(
        scan["FilterExpression"],
        "is_trashed = :trashed AND owner_id = :owner_id"
    );
    assert_eq!(scan["ExpressionAttributeValues"][":owner_id"]["S"], OWNER);
    assert_eq!(scan["ExpressionAttributeValues"][":trashed"]["BOOL"], true);
    let update = requests[1].dynamo_body("UpdateItem", "files");
    assert_eq!(update["Key"]["id"]["S"], OTHER_FILE);
    assert_eq!(
        update["UpdateExpression"],
        "SET is_trashed = :t, updated_at = :u"
    );
    assert_eq!(update["ExpressionAttributeValues"][":t"]["BOOL"], false);
}
