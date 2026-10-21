//! Owner-trust and IDOR regression tests.
//!
//! Handlers run against an in-process fake of the DynamoDB/S3 HTTP APIs and a
//! stub Redis so the full request path (identity extraction, authorization,
//! metadata queries) is exercised without external services.

use super::*;
use crate::models::SharePermission;
use actix_web::{http::StatusCode, test, App, HttpServer};
use serde_json::{json, Map, Value};
use std::collections::{HashMap, HashSet};
use std::sync::{Arc, Mutex};

const FILES: &str = "files";
const FOLDERS: &str = "folders";
const VERSIONS: &str = "versions";
const SHARES: &str = "shares";

type Item = Map<String, Value>;

#[derive(Default)]
struct FakeAws {
    tables: Mutex<HashMap<String, Vec<Item>>>,
    objects: Mutex<HashSet<String>>,
    scans: Mutex<Vec<(String, Option<String>)>>,
}

fn key_matches(table: &str, item: &Item, key: &Item) -> bool {
    if table == VERSIONS {
        item.get("file_id") == key.get("file_id") && item.get("version") == key.get("version")
    } else {
        item.get("id") == key.get("id")
    }
}

fn resolve_name<'a>(name: &'a str, req: &'a Value) -> &'a str {
    if name.starts_with('#') {
        req["ExpressionAttributeNames"][name].as_str().unwrap()
    } else {
        name
    }
}

fn eval_condition(expr: &str, item: &Item, req: &Value) -> bool {
    expr.split(" AND ").map(str::trim).all(|clause| {
        if let Some(attr) = clause
            .strip_prefix("attribute_exists(")
            .and_then(|r| r.strip_suffix(')'))
        {
            item.contains_key(attr)
        } else if let Some(attr) = clause
            .strip_prefix("attribute_not_exists(")
            .and_then(|r| r.strip_suffix(')'))
        {
            !item.contains_key(attr)
        } else {
            let (lhs, rhs) = clause.split_once(" = ").expect("unsupported clause");
            item.get(resolve_name(lhs.trim(), req))
                == Some(&req["ExpressionAttributeValues"][rhs.trim()])
        }
    })
}

fn apply_update(item: &mut Item, req: &Value) {
    let expr = req["UpdateExpression"].as_str().unwrap();
    let (set_part, remove_part) = match expr.split_once(" REMOVE ") {
        Some((s, r)) => (s, Some(r)),
        None => (expr, None),
    };
    for assignment in set_part.trim_start_matches("SET ").split(", ") {
        let (lhs, rhs) = assignment.split_once(" = ").unwrap();
        let value = req["ExpressionAttributeValues"][rhs.trim()].clone();
        item.insert(resolve_name(lhs.trim(), req).to_string(), value);
    }
    if let Some(remove) = remove_part {
        for attr in remove.split(", ") {
            item.remove(attr.trim());
        }
    }
}

fn ddb_json(body: Value) -> HttpResponse {
    HttpResponse::Ok()
        .content_type("application/x-amz-json-1.0")
        .body(body.to_string())
}

async fn fake_aws(
    req: HttpRequest,
    body: web::Bytes,
    state: web::Data<Arc<FakeAws>>,
) -> HttpResponse {
    let Some(target) = req.headers().get("x-amz-target") else {
        // S3 (path-style): only object existence is tracked.
        let path = req.path().to_string();
        let mut objects = state.objects.lock().unwrap();
        return match *req.method() {
            actix_web::http::Method::PUT => {
                objects.insert(path);
                HttpResponse::Ok().finish()
            }
            actix_web::http::Method::DELETE => {
                objects.remove(&path);
                HttpResponse::NoContent().finish()
            }
            _ => HttpResponse::NotImplemented().finish(),
        };
    };
    let op = target
        .to_str()
        .unwrap()
        .rsplit('.')
        .next()
        .unwrap()
        .to_string();
    let r: Value = serde_json::from_slice(&body).unwrap();
    let table = r["TableName"].as_str().unwrap().to_string();
    let mut tables = state.tables.lock().unwrap();
    let rows = tables.entry(table.clone()).or_default();
    match op.as_str() {
        "PutItem" => {
            let item = r["Item"].as_object().unwrap().clone();
            rows.retain(|i| !key_matches(&table, i, &item));
            rows.push(item);
            ddb_json(json!({}))
        }
        "GetItem" => {
            let key = r["Key"].as_object().unwrap();
            match rows.iter().find(|i| key_matches(&table, i, key)) {
                Some(item) => ddb_json(json!({ "Item": item })),
                None => ddb_json(json!({})),
            }
        }
        "DeleteItem" => {
            let key = r["Key"].as_object().unwrap().clone();
            rows.retain(|i| !key_matches(&table, i, &key));
            ddb_json(json!({}))
        }
        "UpdateItem" => {
            let key = r["Key"].as_object().unwrap();
            match rows.iter_mut().find(|i| key_matches(&table, i, key)) {
                Some(item) => {
                    apply_update(item, &r);
                    ddb_json(json!({}))
                }
                None => HttpResponse::BadRequest()
                    .content_type("application/x-amz-json-1.0")
                    .body(
                        json!({
                            "__type": "com.amazonaws.dynamodb.v20120810#ConditionalCheckFailedException",
                            "message": "The conditional request failed"
                        })
                        .to_string(),
                    ),
            }
        }
        "Scan" | "Query" => {
            let expr = r["FilterExpression"]
                .as_str()
                .or_else(|| r["KeyConditionExpression"].as_str())
                .map(str::to_string);
            if op == "Scan" {
                state
                    .scans
                    .lock()
                    .unwrap()
                    .push((table.clone(), expr.clone()));
            }
            let items: Vec<&Item> = rows
                .iter()
                .filter(|i| expr.as_deref().is_none_or(|e| eval_condition(e, i, &r)))
                .collect();
            ddb_json(json!({ "Items": items, "Count": items.len(), "ScannedCount": rows.len() }))
        }
        other => panic!("fake DynamoDB: unsupported operation {other}"),
    }
}

/// Minimal RESP responder: every command gets `:0` (chaos flags are off).
async fn spawn_fake_redis() -> String {
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    actix_rt::spawn(async move {
        while let Ok((mut sock, _)) = listener.accept().await {
            actix_rt::spawn(async move {
                let mut buf = vec![0u8; 4096];
                while let Ok(n) = sock.read(&mut buf).await {
                    if n == 0 {
                        break;
                    }
                    let commands = String::from_utf8_lossy(&buf[..n])
                        .split("\r\n")
                        .filter(|l| l.starts_with('*'))
                        .count();
                    if sock.write_all(&b":0\r\n".repeat(commands)).await.is_err() {
                        break;
                    }
                }
            });
        }
    });
    format!("redis://{addr}")
}

struct Harness {
    state: Arc<FakeAws>,
    meta: MetadataClient,
    s3: S3Client,
    events: EventPublisher,
    redis: redis::aio::ConnectionManager,
    config: AppConfig,
}

impl Harness {
    async fn new() -> Self {
        let state = Arc::new(FakeAws::default());
        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let endpoint = format!("http://{}", listener.local_addr().unwrap());
        let data = web::Data::new(state.clone());
        let server = HttpServer::new(move || {
            App::new()
                .app_data(data.clone())
                .app_data(web::PayloadConfig::new(16 * 1024 * 1024))
                .default_service(web::to(fake_aws))
        })
        .workers(1)
        .listen(listener)
        .unwrap()
        .run();
        actix_rt::spawn(server);

        let creds = aws_sdk_dynamodb::config::Credentials::new("test", "test", None, None, "test");
        let region = aws_sdk_dynamodb::config::Region::new("us-east-1");
        let ddb = aws_sdk_dynamodb::Config::builder()
            .behavior_version(aws_sdk_dynamodb::config::BehaviorVersion::latest())
            .region(region.clone())
            .credentials_provider(creds.clone())
            .endpoint_url(&endpoint)
            .build();
        let s3 = aws_sdk_s3::Config::builder()
            .behavior_version(aws_sdk_s3::config::BehaviorVersion::latest())
            .region(region.clone())
            .credentials_provider(creds.clone())
            .endpoint_url(&endpoint)
            .force_path_style(true)
            .build();
        let sns = aws_sdk_sns::Config::builder()
            .behavior_version(aws_sdk_sns::config::BehaviorVersion::latest())
            .region(region)
            .credentials_provider(creds)
            .endpoint_url(&endpoint)
            .build();

        let redis_url = spawn_fake_redis().await;
        let redis = redis::aio::ConnectionManager::new(redis::Client::open(redis_url).unwrap())
            .await
            .unwrap();

        let mut config = AppConfig::from_env();
        config.server.max_upload_bytes = 1024 * 1024;

        Self {
            state,
            meta: MetadataClient {
                client: aws_sdk_dynamodb::Client::from_conf(ddb),
                files_table: FILES.into(),
                folders_table: FOLDERS.into(),
                versions_table: VERSIONS.into(),
                shares_table: SHARES.into(),
            },
            s3: S3Client {
                client: aws_sdk_s3::Client::from_conf(s3),
                bucket: "test-bucket".into(),
            },
            events: EventPublisher::disabled(aws_sdk_sns::Client::from_conf(sns)),
            redis,
            config,
        }
    }

    async fn seed_file(&self, owner: Uuid) -> FileMetadata {
        let now = Utc::now();
        let id = Uuid::new_v4();
        let file = FileMetadata {
            id,
            name: format!("{id}.txt"),
            mime_type: "text/plain".into(),
            size_bytes: 5,
            s3_key: format!("files/{owner}/{id}"),
            folder_id: None,
            owner_id: owner,
            version: 1,
            is_trashed: false,
            created_at: now,
            updated_at: now,
        };
        self.meta.put_file(&file).await.unwrap();
        self.meta
            .put_version(&FileVersion {
                file_id: id,
                version: 1,
                s3_key: file.s3_key.clone(),
                size_bytes: 5,
                created_by: owner,
                created_at: now,
            })
            .await
            .unwrap();
        file
    }

    async fn seed_folder(&self, owner: Uuid) -> Folder {
        let now = Utc::now();
        let folder = Folder {
            id: Uuid::new_v4(),
            name: "folder".into(),
            parent_id: None,
            owner_id: owner,
            created_at: now,
            updated_at: now,
        };
        self.meta.put_folder(&folder).await.unwrap();
        folder
    }

    async fn seed_share(&self, file: &FileMetadata, with: Uuid, permission: SharePermission) {
        self.meta
            .put_share(&FileShare {
                id: Uuid::new_v4(),
                file_id: file.id,
                shared_with: with,
                permission,
                shared_by: file.owner_id,
                created_at: Utc::now(),
            })
            .await
            .unwrap();
    }

    fn unscoped_scans(&self) -> Vec<(String, Option<String>)> {
        self.state
            .scans
            .lock()
            .unwrap()
            .iter()
            .filter(|(table, expr)| {
                (table == FILES || table == FOLDERS)
                    && !expr.as_deref().unwrap_or("").contains("owner_id")
            })
            .cloned()
            .collect()
    }
}

/// Same route table as `main.rs`, wired to the harness clients.
macro_rules! app {
    ($h:expr) => {{
        let h = &$h;
        test::init_service(
            App::new()
                .app_data(web::Data::new(h.config.clone()))
                .app_data(web::Data::new(h.s3.clone()))
                .app_data(web::Data::new(h.meta.clone()))
                .app_data(web::Data::new(h.events.clone()))
                .app_data(web::Data::new(h.redis.clone()))
                .service(
                    web::scope("/api/v1/files")
                        .route("/upload", web::post().to(upload_file))
                        .route("/shared", web::get().to(list_shared_files))
                        .route("/trash", web::get().to(list_trashed))
                        .route("/activity", web::get().to(list_activity))
                        .route("", web::get().to(list_files))
                        .route("/{file_id}", web::get().to(get_file_metadata))
                        .route("/{file_id}", web::delete().to(delete_file))
                        .route("/{file_id}/download", web::get().to(download_file))
                        .route("/{file_id}/move", web::put().to(move_file))
                        .route("/{file_id}/rename", web::patch().to(rename_file))
                        .route("/{file_id}/versions", web::get().to(list_versions))
                        .route("/{file_id}/trash", web::post().to(trash_file))
                        .route("/{file_id}/restore", web::post().to(restore_file))
                        .route("/{file_id}/share", web::post().to(share_file))
                        .route("/{file_id}/share/{user_id}", web::delete().to(remove_share)),
                )
                .service(
                    web::scope("/api/v1/folders")
                        .route("", web::get().to(list_folders))
                        .route("", web::post().to(create_folder))
                        .route("/{folder_id}", web::get().to(get_folder))
                        .route("/{folder_id}", web::put().to(update_folder))
                        .route("/{folder_id}", web::delete().to(delete_folder)),
                ),
        )
        .await
    }};
}

fn as_user(req: test::TestRequest, user: Uuid) -> test::TestRequest {
    req.insert_header(("X-User-ID", user.to_string()))
}

fn multipart_upload(fields: &[(&str, &str)]) -> (String, Vec<u8>) {
    let boundary = "----otterworks-test-boundary";
    let mut body = String::new();
    for (name, value) in fields {
        body.push_str(&format!(
            "--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n"
        ));
    }
    body.push_str(&format!(
        "--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.txt\"\r\nContent-Type: text/plain\r\n\r\nhello\r\n--{boundary}--\r\n"
    ));
    (
        format!("multipart/form-data; boundary={boundary}"),
        body.into_bytes(),
    )
}

// -- Pure authorization rules --

#[actix_rt::test]
async fn file_access_rules() {
    let owner = Uuid::new_v4();
    let other = Uuid::new_v4();
    let now = Utc::now();
    let file = FileMetadata {
        id: Uuid::new_v4(),
        name: "f".into(),
        mime_type: "text/plain".into(),
        size_bytes: 1,
        s3_key: "k".into(),
        folder_id: None,
        owner_id: owner,
        version: 1,
        is_trashed: false,
        created_at: now,
        updated_at: now,
    };
    let share = |permission| FileShare {
        id: Uuid::new_v4(),
        file_id: file.id,
        shared_with: other,
        permission,
        shared_by: owner,
        created_at: now,
    };
    let viewer = share(SharePermission::Viewer);
    let editor = share(SharePermission::Editor);

    for access in [FileAccess::Read, FileAccess::Write, FileAccess::Owner] {
        assert_eq!(file_access(&file, &owner, None, access), Some(true));
        assert_eq!(file_access(&file, &other, None, access), None);
    }
    assert_eq!(
        file_access(&file, &other, Some(&viewer), FileAccess::Read),
        Some(true)
    );
    assert_eq!(
        file_access(&file, &other, Some(&viewer), FileAccess::Write),
        Some(false)
    );
    assert_eq!(
        file_access(&file, &other, Some(&editor), FileAccess::Write),
        Some(true)
    );
    assert_eq!(
        file_access(&file, &other, Some(&editor), FileAccess::Owner),
        Some(false)
    );
}

#[actix_rt::test]
async fn caller_id_requires_valid_header() {
    let req = test::TestRequest::default().to_http_request();
    assert!(matches!(
        caller_id(&req),
        Err(ServiceError::Unauthorized(_))
    ));

    let req = test::TestRequest::default()
        .insert_header(("X-User-ID", "not-a-uuid"))
        .to_http_request();
    assert!(matches!(
        caller_id(&req),
        Err(ServiceError::Unauthorized(_))
    ));

    let user = Uuid::new_v4();
    let req = test::TestRequest::default()
        .insert_header(("X-User-ID", format!(" {user} ")))
        .to_http_request();
    assert_eq!(caller_id(&req).unwrap(), user);
}

// -- Missing identity header --

#[actix_rt::test]
async fn requests_without_x_user_id_are_rejected_and_never_scan_unscoped() {
    let h = Harness::new().await;
    let app = app!(h);
    let alice = Uuid::new_v4();
    let file = h.seed_file(alice).await;
    let folder = h.seed_folder(alice).await;
    let (ct, body) = multipart_upload(&[("owner_id", &alice.to_string())]);

    let requests = vec![
        test::TestRequest::get().uri("/api/v1/files"),
        test::TestRequest::get().uri(&format!("/api/v1/files?owner_id={alice}")),
        test::TestRequest::get().uri("/api/v1/files/trash"),
        test::TestRequest::get().uri("/api/v1/files/shared"),
        test::TestRequest::get().uri("/api/v1/files/activity"),
        test::TestRequest::get().uri(&format!("/api/v1/folders?owner_id={alice}")),
        test::TestRequest::post()
            .uri("/api/v1/folders")
            .set_json(json!({ "name": "x", "owner_id": alice })),
        test::TestRequest::post()
            .uri("/api/v1/files/upload")
            .insert_header(("content-type", ct))
            .set_payload(body),
        test::TestRequest::get().uri(&format!("/api/v1/files/{}", file.id)),
        test::TestRequest::get().uri(&format!("/api/v1/files/{}/download", file.id)),
        test::TestRequest::delete().uri(&format!("/api/v1/files/{}", file.id)),
        test::TestRequest::get().uri(&format!("/api/v1/folders/{}", folder.id)),
        test::TestRequest::post()
            .uri("/api/v1/files/upload")
            .insert_header(("X-User-ID", "not-a-uuid")),
    ];
    for req in requests {
        let req = req.to_request();
        let uri = req.uri().to_string();
        let resp = test::call_service(&app, req).await;
        assert_eq!(resp.status(), StatusCode::UNAUTHORIZED, "{uri}");
    }

    assert!(h.unscoped_scans().is_empty(), "{:?}", h.unscoped_scans());
    assert!(h.meta.get_file(&file.id).await.is_ok());
    assert!(h.state.objects.lock().unwrap().is_empty());
}

// -- Spoofed owner_id --

#[actix_rt::test]
async fn query_owner_id_cannot_list_another_users_files_or_folders() {
    let h = Harness::new().await;
    let app = app!(h);
    let (alice, bob) = (Uuid::new_v4(), Uuid::new_v4());
    let alice_file = h.seed_file(alice).await;
    let bob_file = h.seed_file(bob).await;
    h.seed_folder(alice).await;
    let bob_folder = h.seed_folder(bob).await;

    let req = as_user(test::TestRequest::get(), bob)
        .uri(&format!("/api/v1/files?owner_id={alice}"))
        .to_request();
    let body: Value = test::call_and_read_body_json(&app, req).await;
    let ids: Vec<&str> = body["files"]
        .as_array()
        .unwrap()
        .iter()
        .map(|f| f["id"].as_str().unwrap())
        .collect();
    assert_eq!(ids, vec![bob_file.id.to_string()]);
    assert!(!ids.contains(&alice_file.id.to_string().as_str()));

    let req = as_user(test::TestRequest::get(), bob)
        .uri(&format!("/api/v1/folders?owner_id={alice}"))
        .to_request();
    let body: Value = test::call_and_read_body_json(&app, req).await;
    let folders = body["folders"].as_array().unwrap();
    assert_eq!(folders.len(), 1);
    assert_eq!(folders[0]["id"], bob_folder.id.to_string());

    h.meta.trash_file(&alice_file.id).await.unwrap();
    let req = as_user(test::TestRequest::get(), bob)
        .uri(&format!("/api/v1/files/trash?owner_id={alice}"))
        .to_request();
    let body: Value = test::call_and_read_body_json(&app, req).await;
    assert_eq!(body["total"], 0);

    assert!(h.unscoped_scans().is_empty(), "{:?}", h.unscoped_scans());
}

#[actix_rt::test]
async fn upload_ignores_multipart_owner_id() {
    let h = Harness::new().await;
    let app = app!(h);
    let (alice, mallory) = (Uuid::new_v4(), Uuid::new_v4());

    let (ct, body) = multipart_upload(&[("owner_id", &alice.to_string())]);
    let req = as_user(test::TestRequest::post(), mallory)
        .uri("/api/v1/files/upload")
        .insert_header(("content-type", ct))
        .set_payload(body)
        .to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::CREATED);
    let body: Value = test::read_body_json(resp).await;
    assert_eq!(body["file"]["owner_id"], mallory.to_string());
    assert!(body["file"]["s3_key"]
        .as_str()
        .unwrap()
        .starts_with(&format!("files/{mallory}/")));

    let id: Uuid = body["file"]["id"].as_str().unwrap().parse().unwrap();
    assert_eq!(h.meta.get_file(&id).await.unwrap().owner_id, mallory);
}

#[actix_rt::test]
async fn upload_into_another_users_folder_is_not_found() {
    let h = Harness::new().await;
    let app = app!(h);
    let (alice, mallory) = (Uuid::new_v4(), Uuid::new_v4());
    let folder = h.seed_folder(alice).await;

    let (ct, body) = multipart_upload(&[("folder_id", &folder.id.to_string())]);
    let req = as_user(test::TestRequest::post(), mallory)
        .uri("/api/v1/files/upload")
        .insert_header(("content-type", ct))
        .set_payload(body)
        .to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::NOT_FOUND);
    assert!(h.state.objects.lock().unwrap().is_empty());
}

#[actix_rt::test]
async fn create_folder_ignores_body_owner_id_and_foreign_parent() {
    let h = Harness::new().await;
    let app = app!(h);
    let (alice, mallory) = (Uuid::new_v4(), Uuid::new_v4());

    let req = as_user(test::TestRequest::post(), mallory)
        .uri("/api/v1/folders")
        .set_json(json!({ "name": "spoof", "owner_id": alice }))
        .to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::CREATED);
    let body: Value = test::read_body_json(resp).await;
    assert_eq!(body["owner_id"], mallory.to_string());

    let alice_folder = h.seed_folder(alice).await;
    let req = as_user(test::TestRequest::post(), mallory)
        .uri("/api/v1/folders")
        .set_json(json!({ "name": "nested", "parent_id": alice_folder.id }))
        .to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::NOT_FOUND);
}

#[actix_rt::test]
async fn share_sets_shared_by_from_caller_not_body() {
    let h = Harness::new().await;
    let app = app!(h);
    let (alice, bob, someone) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
    let file = h.seed_file(alice).await;

    let req = as_user(test::TestRequest::post(), alice)
        .uri(&format!("/api/v1/files/{}/share", file.id))
        .set_json(json!({ "shared_with": bob, "permission": "viewer", "shared_by": someone }))
        .to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::CREATED);
    let body: Value = test::read_body_json(resp).await;
    assert_eq!(body["share"]["shared_by"], alice.to_string());
    assert_eq!(body["share"]["shared_with"], bob.to_string());
}

// -- Cross-user by-id access --

#[actix_rt::test]
async fn cross_user_by_id_access_returns_404_and_changes_nothing() {
    let h = Harness::new().await;
    let app = app!(h);
    let (alice, mallory, carol) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
    let file = h.seed_file(alice).await;
    let folder = h.seed_folder(alice).await;
    let mallory_folder = h.seed_folder(mallory).await;
    h.seed_share(&file, carol, SharePermission::Viewer).await;
    let f = file.id;

    let requests = vec![
        test::TestRequest::get().uri(&format!("/api/v1/files/{f}")),
        test::TestRequest::get().uri(&format!("/api/v1/files/{f}/download")),
        test::TestRequest::get().uri(&format!("/api/v1/files/{f}/versions")),
        test::TestRequest::delete().uri(&format!("/api/v1/files/{f}")),
        test::TestRequest::put()
            .uri(&format!("/api/v1/files/{f}/move"))
            .set_json(json!({ "folder_id": mallory_folder.id })),
        test::TestRequest::patch()
            .uri(&format!("/api/v1/files/{f}/rename"))
            .set_json(json!({ "name": "pwned" })),
        test::TestRequest::post().uri(&format!("/api/v1/files/{f}/trash")),
        test::TestRequest::post().uri(&format!("/api/v1/files/{f}/restore")),
        test::TestRequest::post()
            .uri(&format!("/api/v1/files/{f}/share"))
            .set_json(
                json!({ "shared_with": mallory, "permission": "editor", "shared_by": alice }),
            ),
        test::TestRequest::delete().uri(&format!("/api/v1/files/{f}/share/{carol}")),
        test::TestRequest::get().uri(&format!("/api/v1/folders/{}", folder.id)),
        test::TestRequest::put()
            .uri(&format!("/api/v1/folders/{}", folder.id))
            .set_json(json!({ "name": "pwned" })),
        test::TestRequest::delete().uri(&format!("/api/v1/folders/{}", folder.id)),
    ];
    for req in requests {
        let req = as_user(req, mallory).to_request();
        let label = format!("{} {}", req.method(), req.uri());
        let resp = test::call_service(&app, req).await;
        assert_eq!(resp.status(), StatusCode::NOT_FOUND, "{label}");
        let body: Value = test::read_body_json(resp).await;
        assert!(
            !body.to_string().contains(&alice.to_string()),
            "{label} leaked owner"
        );
    }

    let stored = h.meta.get_file(&f).await.unwrap();
    assert_eq!(stored.name, file.name);
    assert_eq!(stored.folder_id, None);
    assert!(!stored.is_trashed);
    assert!(h
        .meta
        .find_existing_share(&f, &mallory)
        .await
        .unwrap()
        .is_none());
    assert!(h
        .meta
        .find_existing_share(&f, &carol)
        .await
        .unwrap()
        .is_some());
    assert_eq!(h.meta.get_folder(&folder.id).await.unwrap().name, "folder");

    // A non-owner cannot nest their folder under (or move it into) a foreign folder.
    let req = as_user(test::TestRequest::put(), mallory)
        .uri(&format!("/api/v1/folders/{}", mallory_folder.id))
        .set_json(json!({ "parent_id": folder.id }))
        .to_request();
    assert_eq!(
        test::call_service(&app, req).await.status(),
        StatusCode::NOT_FOUND
    );

    // Owner cannot move a file into someone else's folder either.
    let req = as_user(test::TestRequest::put(), alice)
        .uri(&format!("/api/v1/files/{f}/move"))
        .set_json(json!({ "folder_id": mallory_folder.id }))
        .to_request();
    assert_eq!(
        test::call_service(&app, req).await.status(),
        StatusCode::NOT_FOUND
    );
}

// -- Legitimate behavior --

#[actix_rt::test]
async fn owner_retains_full_access() {
    let h = Harness::new().await;
    let app = app!(h);
    let (alice, bob) = (Uuid::new_v4(), Uuid::new_v4());
    let file = h.seed_file(alice).await;
    let folder = h.seed_folder(alice).await;
    let f = file.id;

    let ok = |req: test::TestRequest| as_user(req, alice).to_request();
    let cases = vec![
        (
            ok(test::TestRequest::get().uri(&format!("/api/v1/files/{f}"))),
            StatusCode::OK,
        ),
        (
            ok(test::TestRequest::get().uri(&format!("/api/v1/files/{f}/download"))),
            StatusCode::OK,
        ),
        (
            ok(test::TestRequest::get().uri(&format!("/api/v1/files/{f}/versions"))),
            StatusCode::OK,
        ),
        (
            ok(test::TestRequest::patch()
                .uri(&format!("/api/v1/files/{f}/rename"))
                .set_json(json!({ "name": "renamed.txt" }))),
            StatusCode::OK,
        ),
        (
            ok(test::TestRequest::put()
                .uri(&format!("/api/v1/files/{f}/move"))
                .set_json(json!({ "folder_id": folder.id }))),
            StatusCode::OK,
        ),
        (
            ok(test::TestRequest::post()
                .uri(&format!("/api/v1/files/{f}/share"))
                .set_json(json!({ "shared_with": bob, "permission": "viewer" }))),
            StatusCode::CREATED,
        ),
        (
            ok(test::TestRequest::delete().uri(&format!("/api/v1/files/{f}/share/{bob}"))),
            StatusCode::NO_CONTENT,
        ),
        (
            ok(test::TestRequest::post().uri(&format!("/api/v1/files/{f}/trash"))),
            StatusCode::OK,
        ),
        (
            ok(test::TestRequest::post().uri(&format!("/api/v1/files/{f}/restore"))),
            StatusCode::OK,
        ),
        (
            ok(test::TestRequest::get().uri(&format!("/api/v1/folders/{}", folder.id))),
            StatusCode::OK,
        ),
        (
            ok(test::TestRequest::put()
                .uri(&format!("/api/v1/folders/{}", folder.id))
                .set_json(json!({ "name": "renamed" }))),
            StatusCode::OK,
        ),
        (
            ok(test::TestRequest::delete().uri(&format!("/api/v1/files/{f}"))),
            StatusCode::NO_CONTENT,
        ),
        (
            ok(test::TestRequest::delete().uri(&format!("/api/v1/folders/{}", folder.id))),
            StatusCode::NO_CONTENT,
        ),
    ];
    for (req, expected) in cases {
        let label = format!("{} {}", req.method(), req.uri());
        let resp = test::call_service(&app, req).await;
        assert_eq!(resp.status(), expected, "{label}");
    }
    assert!(h.meta.get_file(&f).await.is_err());
    assert!(h.meta.get_folder(&folder.id).await.is_err());
}

#[actix_rt::test]
async fn share_recipients_get_permission_scoped_access() {
    let h = Harness::new().await;
    let app = app!(h);
    let (alice, viewer, editor) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
    let file = h.seed_file(alice).await;
    h.seed_share(&file, viewer, SharePermission::Viewer).await;
    h.seed_share(&file, editor, SharePermission::Editor).await;
    let f = file.id;

    for user in [viewer, editor] {
        for uri in [
            format!("/api/v1/files/{f}"),
            format!("/api/v1/files/{f}/download"),
            format!("/api/v1/files/{f}/versions"),
        ] {
            let req = as_user(test::TestRequest::get().uri(&uri), user).to_request();
            assert_eq!(
                test::call_service(&app, req).await.status(),
                StatusCode::OK,
                "{uri}"
            );
        }
        let req = as_user(test::TestRequest::get(), user)
            .uri("/api/v1/files/shared")
            .to_request();
        let body: Value = test::call_and_read_body_json(&app, req).await;
        assert_eq!(body["files"][0]["id"], f.to_string());
    }

    let rename = |user| {
        as_user(test::TestRequest::patch(), user)
            .uri(&format!("/api/v1/files/{f}/rename"))
            .set_json(json!({ "name": "edited.txt" }))
            .to_request()
    };
    assert_eq!(
        test::call_service(&app, rename(viewer)).await.status(),
        StatusCode::FORBIDDEN
    );
    assert_eq!(
        test::call_service(&app, rename(editor)).await.status(),
        StatusCode::OK
    );

    // Recipients cannot delete, trash or re-share the owner's file.
    for user in [viewer, editor] {
        for req in [
            test::TestRequest::delete().uri(&format!("/api/v1/files/{f}")),
            test::TestRequest::post().uri(&format!("/api/v1/files/{f}/trash")),
            test::TestRequest::post()
                .uri(&format!("/api/v1/files/{f}/share"))
                .set_json(json!({ "shared_with": Uuid::new_v4(), "permission": "editor" })),
            test::TestRequest::delete().uri(&format!("/api/v1/files/{f}/share/{alice}")),
        ] {
            let req = as_user(req, user).to_request();
            let label = format!("{} {}", req.method(), req.uri());
            assert_eq!(
                test::call_service(&app, req).await.status(),
                StatusCode::FORBIDDEN,
                "{label}"
            );
        }
    }
    assert!(h.meta.get_file(&f).await.is_ok());

    // A recipient may remove their own share.
    let req = as_user(test::TestRequest::delete(), viewer)
        .uri(&format!("/api/v1/files/{f}/share/{viewer}"))
        .to_request();
    assert_eq!(
        test::call_service(&app, req).await.status(),
        StatusCode::NO_CONTENT
    );
    let req = as_user(test::TestRequest::get(), viewer)
        .uri(&format!("/api/v1/files/{f}"))
        .to_request();
    assert_eq!(
        test::call_service(&app, req).await.status(),
        StatusCode::NOT_FOUND
    );
}
