//! Unit tests for the file-sharing surface: share models, permission parsing,
//! and the request validation the share handlers perform before touching DynamoDB.

use actix_web::{http::StatusCode, test as atest, web, App};
use chrono::Utc;
use uuid::Uuid;

use crate::config::{AwsConfig, SnsConfig};
use crate::errors::ServiceError;
use crate::events::EventPublisher;
use crate::handlers;
use crate::metadata::MetadataClient;
use crate::models::{FileShare, ShareFileRequest, ShareFileResponse, SharePermission};

fn unreachable_aws_config() -> AwsConfig {
    AwsConfig {
        region: "us-east-1".into(),
        endpoint_url: Some("http://127.0.0.1:9".into()),
        s3_bucket: "test-bucket".into(),
        dynamodb_table: "files".into(),
        dynamodb_folders_table: "folders".into(),
        dynamodb_versions_table: "versions".into(),
        dynamodb_shares_table: "shares".into(),
    }
}

macro_rules! share_app {
    () => {{
        let aws = unreachable_aws_config();
        let meta = MetadataClient::new(&aws).await;
        let events = EventPublisher::new(&SnsConfig { topic_arn: None }, &aws).await;
        atest::init_service(
            App::new()
                .app_data(web::Data::new(meta))
                .app_data(web::Data::new(events))
                .service(
                    web::scope("/api/v1/files")
                        .route("/shared", web::get().to(handlers::list_shared_files))
                        .route("/{file_id}/share", web::post().to(handlers::share_file))
                        .route(
                            "/{file_id}/share/{user_id}",
                            web::delete().to(handlers::remove_share),
                        ),
                ),
        )
        .await
    }};
}

fn share_body(permission: &str) -> serde_json::Value {
    serde_json::json!({
        "shared_with": Uuid::new_v4(),
        "permission": permission,
        "shared_by": Uuid::new_v4(),
    })
}

// ── SharePermission ────────────────────────────────────────────────────

#[test]
fn permission_serializes_lowercase() {
    assert_eq!(
        serde_json::to_string(&SharePermission::Viewer).unwrap(),
        "\"viewer\""
    );
    assert_eq!(
        serde_json::to_string(&SharePermission::Editor).unwrap(),
        "\"editor\""
    );
}

#[test]
fn permission_deserializes_known_values() {
    let viewer: SharePermission = serde_json::from_str("\"viewer\"").unwrap();
    let editor: SharePermission = serde_json::from_str("\"editor\"").unwrap();
    assert_eq!(viewer, SharePermission::Viewer);
    assert_eq!(editor, SharePermission::Editor);
}

#[test]
fn permission_rejects_unknown_and_frontend_aliases() {
    for raw in [
        "\"owner\"",
        "\"admin\"",
        "\"view\"",
        "\"edit\"",
        "\"\"",
        "\"VIEWER\"",
    ] {
        assert!(
            serde_json::from_str::<SharePermission>(raw).is_err(),
            "{raw} must not deserialize as a share permission"
        );
    }
}

#[test]
fn permission_display_matches_storage_value() {
    assert_eq!(SharePermission::Viewer.to_string(), "viewer");
    assert_eq!(SharePermission::Editor.to_string(), "editor");
}

#[test]
fn permission_from_str_value_is_case_insensitive() {
    assert_eq!(
        SharePermission::from_str_value("Viewer"),
        Some(SharePermission::Viewer)
    );
    assert_eq!(
        SharePermission::from_str_value("EDITOR"),
        Some(SharePermission::Editor)
    );
    assert_eq!(SharePermission::from_str_value("owner"), None);
    assert_eq!(SharePermission::from_str_value(""), None);
}

#[test]
fn permission_display_round_trips_through_from_str_value() {
    for p in [SharePermission::Viewer, SharePermission::Editor] {
        assert_eq!(SharePermission::from_str_value(&p.to_string()), Some(p));
    }
}

// ── ShareFileRequest / FileShare ───────────────────────────────────────

#[test]
fn share_request_deserializes() {
    let with = Uuid::new_v4();
    let by = Uuid::new_v4();
    let raw = format!(r#"{{"shared_with":"{with}","permission":"editor","shared_by":"{by}"}}"#);
    let req: ShareFileRequest = serde_json::from_str(&raw).unwrap();
    assert_eq!(req.shared_with, with);
    assert_eq!(req.shared_by, by);
    assert_eq!(req.permission, SharePermission::Editor);
}

#[test]
fn share_request_requires_all_fields() {
    let with = Uuid::new_v4();
    let missing_permission = format!(r#"{{"shared_with":"{with}","shared_by":"{with}"}}"#);
    let missing_target = format!(r#"{{"permission":"viewer","shared_by":"{with}"}}"#);
    assert!(serde_json::from_str::<ShareFileRequest>(&missing_permission).is_err());
    assert!(serde_json::from_str::<ShareFileRequest>(&missing_target).is_err());
}

#[test]
fn share_request_rejects_non_uuid_user() {
    let raw = r#"{"shared_with":"alice@example.com","permission":"viewer","shared_by":"bob"}"#;
    assert!(serde_json::from_str::<ShareFileRequest>(raw).is_err());
}

#[test]
fn file_share_serializes_snake_case_fields() {
    let share = FileShare {
        id: Uuid::new_v4(),
        file_id: Uuid::new_v4(),
        shared_with: Uuid::new_v4(),
        permission: SharePermission::Viewer,
        shared_by: Uuid::new_v4(),
        created_at: Utc::now(),
    };
    let value = serde_json::to_value(ShareFileResponse {
        share: share.clone(),
    })
    .unwrap();
    let body = &value["share"];
    assert_eq!(body["id"], share.id.to_string());
    assert_eq!(body["file_id"], share.file_id.to_string());
    assert_eq!(body["shared_with"], share.shared_with.to_string());
    assert_eq!(body["shared_by"], share.shared_by.to_string());
    assert_eq!(body["permission"], "viewer");
    assert!(body["created_at"].is_string());
}

#[test]
fn file_share_round_trips() {
    let share = FileShare {
        id: Uuid::new_v4(),
        file_id: Uuid::new_v4(),
        shared_with: Uuid::new_v4(),
        permission: SharePermission::Editor,
        shared_by: Uuid::new_v4(),
        created_at: Utc::now(),
    };
    let decoded: FileShare = serde_json::from_str(&serde_json::to_string(&share).unwrap()).unwrap();
    assert_eq!(decoded.id, share.id);
    assert_eq!(decoded.permission, SharePermission::Editor);
    assert_eq!(decoded.created_at, share.created_at);
}

#[test]
fn share_not_found_maps_to_404() {
    use actix_web::ResponseError;
    let err = ServiceError::ShareNotFound("Share not found".into());
    assert_eq!(err.error_response().status(), StatusCode::NOT_FOUND);
}

#[test]
fn forbidden_maps_to_403() {
    use actix_web::ResponseError;
    let err = ServiceError::Forbidden("not the owner".into());
    assert_eq!(err.error_response().status(), StatusCode::FORBIDDEN);
}

// ── Handler validation (no DynamoDB round trip) ───────────────────────

#[actix_rt::test]
async fn list_shared_requires_user_header() {
    let app = share_app!();
    let req = atest::TestRequest::get()
        .uri("/api/v1/files/shared")
        .to_request();
    let resp = atest::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::BAD_REQUEST);
}

#[actix_rt::test]
async fn list_shared_rejects_non_uuid_user_header() {
    let app = share_app!();
    let req = atest::TestRequest::get()
        .uri("/api/v1/files/shared")
        .insert_header(("X-User-ID", "not-a-uuid"))
        .to_request();
    let resp = atest::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::BAD_REQUEST);
}

#[actix_rt::test]
async fn share_rejects_invalid_file_id() {
    let app = share_app!();
    let req = atest::TestRequest::post()
        .uri("/api/v1/files/not-a-uuid/share")
        .set_json(share_body("viewer"))
        .to_request();
    let resp = atest::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::BAD_REQUEST);
}

#[actix_rt::test]
async fn share_rejects_unknown_permission() {
    let app = share_app!();
    let req = atest::TestRequest::post()
        .uri(&format!("/api/v1/files/{}/share", Uuid::new_v4()))
        .set_json(share_body("owner"))
        .to_request();
    let resp = atest::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::BAD_REQUEST);
}

#[actix_rt::test]
async fn share_rejects_missing_body() {
    let app = share_app!();
    let req = atest::TestRequest::post()
        .uri(&format!("/api/v1/files/{}/share", Uuid::new_v4()))
        .insert_header(("content-type", "application/json"))
        .set_payload("{}")
        .to_request();
    let resp = atest::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::BAD_REQUEST);
}

#[actix_rt::test]
async fn remove_share_rejects_invalid_file_id() {
    let app = share_app!();
    let req = atest::TestRequest::delete()
        .uri(&format!("/api/v1/files/nope/share/{}", Uuid::new_v4()))
        .to_request();
    let resp = atest::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::BAD_REQUEST);
}

#[actix_rt::test]
async fn remove_share_rejects_invalid_user_id() {
    let app = share_app!();
    let req = atest::TestRequest::delete()
        .uri(&format!("/api/v1/files/{}/share/nope", Uuid::new_v4()))
        .to_request();
    let resp = atest::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::BAD_REQUEST);
}
