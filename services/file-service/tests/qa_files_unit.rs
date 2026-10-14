//! QA unit tests for the file-service (files area).
//!
//! file-service is a binary crate (no lib.rs), so the source modules are
//! compiled into this test crate with `#[path]` instead of being imported.
#![allow(dead_code, unused_imports)]

#[path = "../src/config.rs"]
mod config;
#[path = "../src/errors.rs"]
mod errors;
#[path = "../src/events.rs"]
mod events;
#[path = "../src/handlers.rs"]
mod handlers;
#[path = "../src/metadata.rs"]
mod metadata;
#[path = "../src/middleware.rs"]
mod middleware;
#[path = "../src/models.rs"]
mod models;
#[path = "../src/storage.rs"]
mod storage;

use actix_web::http::StatusCode;
use actix_web::{test, web, App, ResponseError};
use chrono::Utc;
use uuid::Uuid;

use config::{AppConfig, AwsConfig, ServerConfig, SnsConfig};
use errors::ServiceError;
use models::*;

fn offlineAwsConfig() -> AwsConfig {
    AwsConfig {
        region: "us-east-1".into(),
        endpoint_url: Some("http://127.0.0.1:1".into()),
        s3_bucket: "qa-bucket".into(),
        dynamodb_table: "qa-files".into(),
        dynamodb_folders_table: "qa-folders".into(),
        dynamodb_versions_table: "qa-versions".into(),
        dynamodb_shares_table: "qa-shares".into(),
    }
}

macro_rules! qaApp {
    () => {{
        std::env::set_var("AWS_ACCESS_KEY_ID", "test");
        std::env::set_var("AWS_SECRET_ACCESS_KEY", "test");
        let awsCfg = offlineAwsConfig();
        let snsCfg = SnsConfig { topic_arn: None };
        let appCfg = AppConfig {
            server: ServerConfig { port: 0, max_upload_bytes: 1024 },
            aws: awsCfg.clone(),
            sns: snsCfg.clone(),
        };
        let meta = metadata::MetadataClient::new(&awsCfg).await;
        let s3 = storage::S3Client::new(&awsCfg).await;
        let ev = events::EventPublisher::new(&snsCfg, &awsCfg).await;
        test::init_service(
            App::new()
                .app_data(web::Data::new(appCfg))
                .app_data(web::Data::new(meta))
                .app_data(web::Data::new(s3))
                .app_data(web::Data::new(ev))
                .route("/health", web::get().to(handlers::health))
                .service(
                    web::scope("/api/v1/files")
                        .route("/shared", web::get().to(handlers::list_shared_files))
                        .route("/activity", web::get().to(handlers::list_activity))
                        .route("/{file_id}", web::get().to(handlers::get_file_metadata))
                        .route("/{file_id}", web::delete().to(handlers::delete_file))
                        .route("/{file_id}/download", web::get().to(handlers::download_file))
                        .route("/{file_id}/move", web::put().to(handlers::move_file))
                        .route("/{file_id}/rename", web::patch().to(handlers::rename_file))
                        .route("/{file_id}/versions", web::get().to(handlers::list_versions))
                        .route("/{file_id}/trash", web::post().to(handlers::trash_file))
                        .route("/{file_id}/restore", web::post().to(handlers::restore_file))
                        .route("/{file_id}/share", web::post().to(handlers::share_file)),
                ),
        )
        .await
    }};
}

async fn bodyJson(resp: actix_web::dev::ServiceResponse) -> serde_json::Value {
    let bytes = test::read_body(resp).await;
    serde_json::from_slice(&bytes).expect("json body")
}

fn sampleFile() -> FileMetadata {
    let now = Utc::now();
    FileMetadata {
        id: Uuid::new_v4(),
        name: "report.pdf".into(),
        mime_type: "application/pdf".into(),
        size_bytes: 2048,
        s3_key: "files/owner/id".into(),
        folder_id: None,
        owner_id: Uuid::new_v4(),
        version: 1,
        is_trashed: false,
        created_at: now,
        updated_at: now,
    }
}

// ── Error mapping ────────────────────────────────────────────────────

#[actix_rt::test]
async fn fileTooLargeMapsTo413WithStableErrorCode() {
    let err = ServiceError::FileTooLarge { max_bytes: 10, actual_bytes: 11 };
    let resp = err.error_response();
    assert_eq!(resp.status(), StatusCode::PAYLOAD_TOO_LARGE);
    let body = actix_web::body::to_bytes(resp.into_body()).await.unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
    assert_eq!(json["error"], "file_too_large");
    assert!(json["message"].as_str().unwrap().contains("max 10 bytes"));
}

#[actix_rt::test]
async fn notFoundErrorsMapTo404() {
    for err in [
        ServiceError::FileNotFound("x".into()),
        ServiceError::FolderNotFound("x".into()),
        ServiceError::VersionNotFound("x".into()),
        ServiceError::ShareNotFound("x".into()),
    ] {
        assert_eq!(err.error_response().status(), StatusCode::NOT_FOUND);
    }
}

#[actix_rt::test]
async fn clientAndServerErrorsMapToExpectedStatus() {
    assert_eq!(ServiceError::BadRequest("b".into()).error_response().status(), StatusCode::BAD_REQUEST);
    assert_eq!(ServiceError::Unauthorized("u".into()).error_response().status(), StatusCode::UNAUTHORIZED);
    assert_eq!(ServiceError::Forbidden("f".into()).error_response().status(), StatusCode::FORBIDDEN);
    assert_eq!(ServiceError::S3Error("s".into()).error_response().status(), StatusCode::INTERNAL_SERVER_ERROR);
    assert_eq!(ServiceError::DynamoError("d".into()).error_response().status(), StatusCode::INTERNAL_SERVER_ERROR);
}

#[actix_rt::test]
async fn storageErrorUsesStorageErrorCode() {
    let resp = ServiceError::S3Error("boom".into()).error_response();
    let body = actix_web::body::to_bytes(resp.into_body()).await.unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
    assert_eq!(json["error"], "storage_error");
}

// ── Config ───────────────────────────────────────────────────────────

#[actix_rt::test]
async fn maxUploadBytesDefaultsTo100MbAndHonoursOverride() {
    std::env::remove_var("MAX_UPLOAD_BYTES");
    assert_eq!(ServerConfig::from_env().max_upload_bytes, 104_857_600);
    std::env::set_var("MAX_UPLOAD_BYTES", "2048");
    assert_eq!(ServerConfig::from_env().max_upload_bytes, 2048);
    std::env::set_var("MAX_UPLOAD_BYTES", "not-a-number");
    assert_eq!(ServerConfig::from_env().max_upload_bytes, 104_857_600);
    std::env::remove_var("MAX_UPLOAD_BYTES");
}

// ── Models / serde contracts ─────────────────────────────────────────

#[actix_rt::test]
async fn sharePermissionSerializesLowercase() {
    assert_eq!(serde_json::to_string(&SharePermission::Viewer).unwrap(), "\"viewer\"");
    assert_eq!(serde_json::to_string(&SharePermission::Editor).unwrap(), "\"editor\"");
    assert_eq!(SharePermission::Editor.to_string(), "editor");
}

#[actix_rt::test]
async fn shareRequestRejectsUnknownPermission() {
    let body = format!(
        r#"{{"shared_with":"{}","permission":"owner","shared_by":"{}"}}"#,
        Uuid::new_v4(),
        Uuid::new_v4()
    );
    assert!(serde_json::from_str::<ShareFileRequest>(&body).is_err());
}

#[actix_rt::test]
async fn moveRequestAcceptsNullAndMissingFolderAsRoot() {
    let a: MoveFileRequest = serde_json::from_str(r#"{"folder_id":null}"#).unwrap();
    let b: MoveFileRequest = serde_json::from_str("{}").unwrap();
    assert!(a.folder_id.is_none());
    assert!(b.folder_id.is_none());
    let id = Uuid::new_v4();
    let c: MoveFileRequest = serde_json::from_str(&format!(r#"{{"folder_id":"{id}"}}"#)).unwrap();
    assert_eq!(c.folder_id, Some(id));
}

#[actix_rt::test]
async fn renameRequestRequiresName() {
    assert!(serde_json::from_str::<RenameFileRequest>("{}").is_err());
    let r: RenameFileRequest = serde_json::from_str(r#"{"name":"new.txt"}"#).unwrap();
    assert_eq!(r.name, "new.txt");
}

#[actix_rt::test]
async fn fileDetailResponseFlattensMetadataAndIncludesShares() {
    let file = sampleFile();
    let id = file.id;
    let json = serde_json::to_value(FileDetailResponse { file, shared_with: vec![] }).unwrap();
    assert_eq!(json["id"], id.to_string());
    assert_eq!(json["mime_type"], "application/pdf");
    assert_eq!(json["size_bytes"], 2048);
    assert!(json["shared_with"].as_array().unwrap().is_empty());
    assert!(json.get("file").is_none());
}

#[actix_rt::test]
async fn fileMetadataJsonRoundTrips() {
    let file = sampleFile();
    let json = serde_json::to_string(&file).unwrap();
    let back: FileMetadata = serde_json::from_str(&json).unwrap();
    assert_eq!(back.id, file.id);
    assert_eq!(back.name, file.name);
    assert_eq!(back.size_bytes, file.size_bytes);
    assert_eq!(back.is_trashed, file.is_trashed);
}

#[actix_rt::test]
async fn activityItemSerializesTypeField() {
    let item = ActivityItem {
        id: "upload-1".into(),
        activity_type: "upload".into(),
        description: "Uploaded a".into(),
        actor_name: "You".into(),
        resource_name: "a".into(),
        resource_type: "file".into(),
        resource_id: "1".into(),
        created_at: Utc::now().to_rfc3339(),
    };
    let json = serde_json::to_value(item).unwrap();
    assert_eq!(json["type"], "upload");
    assert!(json.get("activity_type").is_none());
}

#[actix_rt::test]
async fn listFilesQueryParsesPaginationAndTrashFlag() {
    let q = web::Query::<ListFilesQuery>::from_query("page=2&page_size=10&include_trashed=true").unwrap();
    assert_eq!(q.page, Some(2));
    assert_eq!(q.page_size, Some(10));
    assert_eq!(q.include_trashed, Some(true));
    assert!(web::Query::<ListFilesQuery>::from_query("folder_id=not-a-uuid").is_err());
}

// ── Handler input validation (no backing store reached) ───────────────

#[actix_rt::test]
async fn healthReportsFileService() {
    let app = qaApp!();
    let resp = test::call_service(&app, test::TestRequest::get().uri("/health").to_request()).await;
    assert_eq!(resp.status(), StatusCode::OK);
    let json = bodyJson(resp).await;
    assert_eq!(json["service"], "file-service");
    assert_eq!(json["status"], "healthy");
}

#[actix_rt::test]
async fn invalidFileIdIsRejectedOnEveryFileRoute() {
    let app = qaApp!();
    let requests = vec![
        test::TestRequest::get().uri("/api/v1/files/not-a-uuid"),
        test::TestRequest::delete().uri("/api/v1/files/not-a-uuid"),
        test::TestRequest::get().uri("/api/v1/files/not-a-uuid/download"),
        test::TestRequest::get().uri("/api/v1/files/not-a-uuid/versions"),
        test::TestRequest::post().uri("/api/v1/files/not-a-uuid/trash"),
        test::TestRequest::post().uri("/api/v1/files/not-a-uuid/restore"),
        test::TestRequest::put()
            .uri("/api/v1/files/not-a-uuid/move")
            .set_json(serde_json::json!({ "folder_id": null })),
        test::TestRequest::patch()
            .uri("/api/v1/files/not-a-uuid/rename")
            .set_json(serde_json::json!({ "name": "x.txt" })),
    ];
    for req in requests {
        let resp = test::call_service(&app, req.to_request()).await;
        assert_eq!(resp.status(), StatusCode::BAD_REQUEST);
        let json = bodyJson(resp).await;
        assert_eq!(json["error"], "bad_request");
        assert!(json["message"].as_str().unwrap().contains("invalid file id"));
    }
}

#[actix_rt::test]
async fn renameRejectsBlankName() {
    let app = qaApp!();
    let req = test::TestRequest::patch()
        .uri(&format!("/api/v1/files/{}/rename", Uuid::new_v4()))
        .set_json(serde_json::json!({ "name": "   " }))
        .to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::BAD_REQUEST);
    let json = bodyJson(resp).await;
    assert!(json["message"].as_str().unwrap().contains("name cannot be empty"));
}

#[actix_rt::test]
async fn renameRejectsMissingNameField() {
    let app = qaApp!();
    let req = test::TestRequest::patch()
        .uri(&format!("/api/v1/files/{}/rename", Uuid::new_v4()))
        .set_json(serde_json::json!({}))
        .to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::BAD_REQUEST);
}

#[actix_rt::test]
async fn moveRejectsMalformedFolderId() {
    let app = qaApp!();
    let req = test::TestRequest::put()
        .uri(&format!("/api/v1/files/{}/move", Uuid::new_v4()))
        .set_json(serde_json::json!({ "folder_id": "nope" }))
        .to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::BAD_REQUEST);
}

#[actix_rt::test]
async fn shareRejectsInvalidPermission() {
    let app = qaApp!();
    let req = test::TestRequest::post()
        .uri(&format!("/api/v1/files/{}/share", Uuid::new_v4()))
        .set_json(serde_json::json!({
            "shared_with": Uuid::new_v4(),
            "permission": "owner",
            "shared_by": Uuid::new_v4(),
        }))
        .to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::BAD_REQUEST);
}

#[actix_rt::test]
async fn sharedAndActivityRequireUserContext() {
    let app = qaApp!();
    for uri in ["/api/v1/files/shared", "/api/v1/files/activity"] {
        let resp = test::call_service(&app, test::TestRequest::get().uri(uri).to_request()).await;
        assert_eq!(resp.status(), StatusCode::BAD_REQUEST, "{uri}");
    }
}
