//! QA unit tests for the files area: error mapping, request/response
//! contracts, and handler input validation that short-circuits before any
//! AWS call (so no LocalStack is required).

use actix_web::{http::StatusCode, test as atest, web, App, ResponseError};
use chrono::Utc;
use uuid::Uuid;

use crate::config::AwsConfig;
use crate::errors::ServiceError;
use crate::events::EventPublisher;
use crate::handlers;
use crate::metadata::MetadataClient;
use crate::models::*;
use crate::storage::S3Client;

fn sample_file() -> FileMetadata {
    let now = Utc::now();
    FileMetadata {
        id: Uuid::new_v4(),
        name: "report.pdf".into(),
        mime_type: "application/pdf".into(),
        size_bytes: 2048,
        s3_key: "files/abc/report.pdf".into(),
        folder_id: None,
        owner_id: Uuid::new_v4(),
        version: 1,
        is_trashed: false,
        created_at: now,
        updated_at: now,
    }
}

async fn error_body(err: ServiceError) -> (StatusCode, serde_json::Value) {
    let resp = err.error_response();
    let status = resp.status();
    let bytes = actix_web::body::to_bytes(resp.into_body()).await.unwrap();
    (status, serde_json::from_slice(&bytes).unwrap())
}

mod error_mapping {
    use super::*;

    #[actix_rt::test]
    async fn not_found_variants_return_404() {
        for err in [
            ServiceError::FileNotFound("x".into()),
            ServiceError::FolderNotFound("x".into()),
            ServiceError::VersionNotFound("x".into()),
            ServiceError::ShareNotFound("x".into()),
        ] {
            let (status, _) = error_body(err).await;
            assert_eq!(status, StatusCode::NOT_FOUND);
        }
    }

    #[actix_rt::test]
    async fn bad_request_returns_400_with_message() {
        let (status, body) =
            error_body(ServiceError::BadRequest("name cannot be empty".into())).await;
        assert_eq!(status, StatusCode::BAD_REQUEST);
        assert!(
            body["message"]
                .as_str()
                .unwrap_or_default()
                .contains("name cannot be empty")
                || body.to_string().contains("name cannot be empty")
        );
    }

    #[actix_rt::test]
    async fn file_too_large_returns_413() {
        let (status, body) = error_body(ServiceError::FileTooLarge {
            max_bytes: 10,
            actual_bytes: 20,
        })
        .await;
        assert_eq!(status, StatusCode::PAYLOAD_TOO_LARGE);
        assert!(body["error"].is_string());
    }

    #[actix_rt::test]
    async fn auth_variants_map_to_401_and_403() {
        assert_eq!(
            error_body(ServiceError::Unauthorized("x".into())).await.0,
            StatusCode::UNAUTHORIZED
        );
        let (status, body) = error_body(ServiceError::Forbidden("x".into())).await;
        assert_eq!(status, StatusCode::FORBIDDEN);
        assert_eq!(body["error"], "forbidden");
    }

    #[actix_rt::test]
    async fn backend_errors_return_typed_5xx() {
        let (s3_status, s3_body) = error_body(ServiceError::S3Error("boom".into())).await;
        assert!(s3_status.is_server_error());
        assert_eq!(s3_body["error"], "storage_error");
        let (dyn_status, dyn_body) = error_body(ServiceError::DynamoError("boom".into())).await;
        assert!(dyn_status.is_server_error());
        assert_eq!(dyn_body["error"], "metadata_error");
        let (sns_status, sns_body) = error_body(ServiceError::SnsError("boom".into())).await;
        assert!(sns_status.is_server_error());
        assert_eq!(sns_body["error"], "event_error");
        let (int_status, int_body) = error_body(ServiceError::Internal("boom".into())).await;
        assert_eq!(int_status, StatusCode::INTERNAL_SERVER_ERROR);
        assert_eq!(int_body["error"], "internal_error");
    }

    #[test]
    fn display_includes_context() {
        let msg = ServiceError::FileTooLarge {
            max_bytes: 10,
            actual_bytes: 20,
        }
        .to_string();
        assert!(msg.contains("10") && msg.contains("20"));
        assert!(ServiceError::FileNotFound("abc".into())
            .to_string()
            .contains("abc"));
    }
}

mod model_contracts {
    use super::*;

    #[test]
    fn share_permission_serializes_lowercase() {
        assert_eq!(
            serde_json::to_value(SharePermission::Viewer).unwrap(),
            "viewer"
        );
        assert_eq!(
            serde_json::to_value(SharePermission::Editor).unwrap(),
            "editor"
        );
        assert_eq!(SharePermission::Editor.to_string(), "editor");
    }

    #[test]
    fn share_permission_rejects_unknown_values() {
        assert!(serde_json::from_str::<SharePermission>("\"owner\"").is_err());
        assert!(SharePermission::from_str_value("admin").is_none());
        assert_eq!(
            SharePermission::from_str_value("VIEWER"),
            Some(SharePermission::Viewer)
        );
    }

    #[test]
    fn file_metadata_roundtrips_through_json() {
        let file = sample_file();
        let json = serde_json::to_value(&file).unwrap();
        assert_eq!(json["name"], "report.pdf");
        assert_eq!(json["size_bytes"], 2048);
        assert_eq!(json["is_trashed"], false);
        let back: FileMetadata = serde_json::from_value(json).unwrap();
        assert_eq!(back.id, file.id);
        assert_eq!(back.version, 1);
    }

    #[test]
    fn file_detail_response_flattens_metadata() {
        let file = sample_file();
        let detail = FileDetailResponse {
            file: file.clone(),
            shared_with: vec![],
        };
        let json = serde_json::to_value(&detail).unwrap();
        assert_eq!(json["id"], file.id.to_string());
        assert!(json.get("file").is_none());
        assert!(json["shared_with"].as_array().unwrap().is_empty());
    }

    #[test]
    fn move_request_accepts_null_folder_for_root() {
        let req: MoveFileRequest = serde_json::from_str(r#"{"folder_id":null}"#).unwrap();
        assert!(req.folder_id.is_none());
        let fid = Uuid::new_v4();
        let req: MoveFileRequest =
            serde_json::from_str(&format!(r#"{{"folder_id":"{fid}"}}"#)).unwrap();
        assert_eq!(req.folder_id, Some(fid));
    }

    #[test]
    fn move_request_rejects_non_uuid_folder() {
        assert!(serde_json::from_str::<MoveFileRequest>(r#"{"folder_id":"nope"}"#).is_err());
    }

    #[test]
    fn rename_request_requires_name() {
        assert!(serde_json::from_str::<RenameFileRequest>("{}").is_err());
        let req: RenameFileRequest = serde_json::from_str(r#"{"name":"a.txt"}"#).unwrap();
        assert_eq!(req.name, "a.txt");
    }

    #[test]
    fn create_folder_request_requires_owner_and_name() {
        assert!(serde_json::from_str::<CreateFolderRequest>(r#"{"name":"x"}"#).is_err());
        let owner = Uuid::new_v4();
        assert!(serde_json::from_str::<CreateFolderRequest>(&format!(
            r#"{{"owner_id":"{owner}"}}"#
        ))
        .is_err());
        let req: CreateFolderRequest =
            serde_json::from_str(&format!(r#"{{"name":"Docs","owner_id":"{owner}"}}"#)).unwrap();
        assert!(req.parent_id.is_none());
    }

    #[test]
    fn update_folder_request_fields_are_optional() {
        let req: UpdateFolderRequest = serde_json::from_str("{}").unwrap();
        assert!(req.name.is_none() && req.parent_id.is_none());
    }

    #[test]
    fn share_request_requires_valid_permission() {
        let a = Uuid::new_v4();
        let b = Uuid::new_v4();
        let ok = format!(r#"{{"shared_with":"{a}","permission":"editor","shared_by":"{b}"}}"#);
        assert_eq!(
            serde_json::from_str::<ShareFileRequest>(&ok)
                .unwrap()
                .permission,
            SharePermission::Editor
        );
        let bad = format!(r#"{{"shared_with":"{a}","permission":"root","shared_by":"{b}"}}"#);
        assert!(serde_json::from_str::<ShareFileRequest>(&bad).is_err());
    }

    #[test]
    fn list_files_query_parses_from_query_string() {
        let fid = Uuid::new_v4();
        let q = web::Query::<ListFilesQuery>::from_query(&format!(
            "folder_id={fid}&page=2&page_size=5&include_trashed=true"
        ))
        .unwrap();
        assert_eq!(q.folder_id, Some(fid));
        assert_eq!(q.page, Some(2));
        assert_eq!(q.page_size, Some(5));
        assert_eq!(q.include_trashed, Some(true));
        assert!(web::Query::<ListFilesQuery>::from_query("folder_id=bad").is_err());
    }

    #[test]
    fn activity_item_serializes_type_key() {
        let item = ActivityItem {
            id: "1".into(),
            activity_type: "upload".into(),
            description: "d".into(),
            actor_name: "a".into(),
            resource_name: "r".into(),
            resource_type: "file".into(),
            resource_id: "x".into(),
            created_at: "now".into(),
        };
        let json = serde_json::to_value(&item).unwrap();
        assert_eq!(json["type"], "upload");
        assert!(json.get("activity_type").is_none());
    }

    #[test]
    fn download_response_shape() {
        let json = serde_json::to_value(DownloadResponse {
            url: "http://x".into(),
            expires_in_secs: 3600,
        })
        .unwrap();
        assert_eq!(json["url"], "http://x");
        assert_eq!(json["expires_in_secs"], 3600);
    }
}

mod handler_validation {
    use super::*;

    fn offline_aws_config() -> AwsConfig {
        AwsConfig {
            region: "us-east-1".into(),
            endpoint_url: Some("http://127.0.0.1:9".into()),
            s3_bucket: "qa-bucket".into(),
            dynamodb_table: "qa-files".into(),
            dynamodb_folders_table: "qa-folders".into(),
            dynamodb_versions_table: "qa-versions".into(),
            dynamodb_shares_table: "qa-shares".into(),
        }
    }

    macro_rules! app {
        () => {{
            let aws = offline_aws_config();
            let meta = MetadataClient::new(&aws).await;
            let s3 = S3Client::new(&aws).await;
            let events =
                EventPublisher::new(&crate::config::SnsConfig { topic_arn: None }, &aws).await;
            atest::init_service(
                App::new()
                    .app_data(web::Data::new(meta))
                    .app_data(web::Data::new(s3))
                    .app_data(web::Data::new(events))
                    .service(
                        web::scope("/api/v1/files")
                            .route("/shared", web::get().to(handlers::list_shared_files))
                            .route("/activity", web::get().to(handlers::list_activity))
                            .route("/{file_id}", web::get().to(handlers::get_file_metadata))
                            .route("/{file_id}", web::delete().to(handlers::delete_file))
                            .route(
                                "/{file_id}/download",
                                web::get().to(handlers::download_file),
                            )
                            .route("/{file_id}/move", web::put().to(handlers::move_file))
                            .route("/{file_id}/rename", web::patch().to(handlers::rename_file))
                            .route(
                                "/{file_id}/versions",
                                web::get().to(handlers::list_versions),
                            )
                            .route("/{file_id}/trash", web::post().to(handlers::trash_file))
                            .route("/{file_id}/restore", web::post().to(handlers::restore_file))
                            .route("/{file_id}/share", web::post().to(handlers::share_file))
                            .route(
                                "/{file_id}/share/{user_id}",
                                web::delete().to(handlers::remove_share),
                            ),
                    )
                    .service(
                        web::scope("/api/v1/folders")
                            .route("", web::post().to(handlers::create_folder))
                            .route("/{folder_id}", web::get().to(handlers::get_folder))
                            .route("/{folder_id}", web::put().to(handlers::update_folder))
                            .route("/{folder_id}", web::delete().to(handlers::delete_folder)),
                    ),
            )
            .await
        }};
    }

    async fn assert_status(req: atest::TestRequest, expected: StatusCode) {
        let app = app!();
        let resp = atest::call_service(&app, req.to_request()).await;
        assert_eq!(resp.status(), expected);
    }

    #[actix_rt::test]
    async fn get_metadata_rejects_invalid_uuid() {
        assert_status(
            atest::TestRequest::get().uri("/api/v1/files/not-a-uuid"),
            StatusCode::BAD_REQUEST,
        )
        .await;
    }

    #[actix_rt::test]
    async fn delete_rejects_invalid_uuid() {
        assert_status(
            atest::TestRequest::delete().uri("/api/v1/files/123"),
            StatusCode::BAD_REQUEST,
        )
        .await;
    }

    #[actix_rt::test]
    async fn download_rejects_invalid_uuid() {
        assert_status(
            atest::TestRequest::get().uri("/api/v1/files/zzz/download"),
            StatusCode::BAD_REQUEST,
        )
        .await;
    }

    #[actix_rt::test]
    async fn versions_rejects_invalid_uuid() {
        assert_status(
            atest::TestRequest::get().uri("/api/v1/files/zzz/versions"),
            StatusCode::BAD_REQUEST,
        )
        .await;
    }

    #[actix_rt::test]
    async fn trash_and_restore_reject_invalid_uuid() {
        assert_status(
            atest::TestRequest::post().uri("/api/v1/files/zzz/trash"),
            StatusCode::BAD_REQUEST,
        )
        .await;
        assert_status(
            atest::TestRequest::post().uri("/api/v1/files/zzz/restore"),
            StatusCode::BAD_REQUEST,
        )
        .await;
    }

    #[actix_rt::test]
    async fn rename_rejects_invalid_uuid() {
        let req = atest::TestRequest::patch()
            .uri("/api/v1/files/zzz/rename")
            .set_json(serde_json::json!({"name": "ok.txt"}));
        assert_status(req, StatusCode::BAD_REQUEST).await;
    }

    #[actix_rt::test]
    async fn rename_rejects_blank_name_before_lookup() {
        let req = atest::TestRequest::patch()
            .uri(&format!("/api/v1/files/{}/rename", Uuid::new_v4()))
            .set_json(serde_json::json!({"name": "   "}));
        assert_status(req, StatusCode::BAD_REQUEST).await;
    }

    #[actix_rt::test]
    async fn rename_rejects_missing_body_field() {
        let req = atest::TestRequest::patch()
            .uri(&format!("/api/v1/files/{}/rename", Uuid::new_v4()))
            .set_json(serde_json::json!({}));
        assert_status(req, StatusCode::BAD_REQUEST).await;
    }

    #[actix_rt::test]
    async fn move_rejects_invalid_uuid() {
        let req = atest::TestRequest::put()
            .uri("/api/v1/files/zzz/move")
            .set_json(serde_json::json!({"folder_id": null}));
        assert_status(req, StatusCode::BAD_REQUEST).await;
    }

    #[actix_rt::test]
    async fn move_rejects_malformed_folder_id() {
        let req = atest::TestRequest::put()
            .uri(&format!("/api/v1/files/{}/move", Uuid::new_v4()))
            .set_json(serde_json::json!({"folder_id": "nope"}));
        assert_status(req, StatusCode::BAD_REQUEST).await;
    }

    #[actix_rt::test]
    async fn share_rejects_invalid_permission() {
        let req = atest::TestRequest::post()
            .uri(&format!("/api/v1/files/{}/share", Uuid::new_v4()))
            .set_json(serde_json::json!({
                "shared_with": Uuid::new_v4(), "permission": "owner", "shared_by": Uuid::new_v4()
            }));
        assert_status(req, StatusCode::BAD_REQUEST).await;
    }

    #[actix_rt::test]
    async fn remove_share_rejects_invalid_ids() {
        assert_status(
            atest::TestRequest::delete()
                .uri(&format!("/api/v1/files/bad/share/{}", Uuid::new_v4())),
            StatusCode::BAD_REQUEST,
        )
        .await;
        assert_status(
            atest::TestRequest::delete()
                .uri(&format!("/api/v1/files/{}/share/bad", Uuid::new_v4())),
            StatusCode::BAD_REQUEST,
        )
        .await;
    }

    #[actix_rt::test]
    async fn shared_list_requires_user_header() {
        assert_status(
            atest::TestRequest::get().uri("/api/v1/files/shared"),
            StatusCode::BAD_REQUEST,
        )
        .await;
    }

    #[actix_rt::test]
    async fn shared_list_rejects_malformed_user_header() {
        let req = atest::TestRequest::get()
            .uri("/api/v1/files/shared")
            .insert_header(("X-User-ID", "nope"));
        assert_status(req, StatusCode::BAD_REQUEST).await;
    }

    #[actix_rt::test]
    async fn activity_requires_owner_context() {
        assert_status(
            atest::TestRequest::get().uri("/api/v1/files/activity"),
            StatusCode::BAD_REQUEST,
        )
        .await;
    }

    #[actix_rt::test]
    async fn create_folder_requires_owner_id() {
        let req = atest::TestRequest::post()
            .uri("/api/v1/folders")
            .set_json(serde_json::json!({"name": "Docs"}));
        assert_status(req, StatusCode::BAD_REQUEST).await;
    }

    #[actix_rt::test]
    async fn folder_routes_reject_invalid_uuid() {
        assert_status(
            atest::TestRequest::get().uri("/api/v1/folders/bad"),
            StatusCode::BAD_REQUEST,
        )
        .await;
        assert_status(
            atest::TestRequest::put()
                .uri("/api/v1/folders/bad")
                .set_json(serde_json::json!({"name": "x"})),
            StatusCode::BAD_REQUEST,
        )
        .await;
        assert_status(
            atest::TestRequest::delete().uri("/api/v1/folders/bad"),
            StatusCode::BAD_REQUEST,
        )
        .await;
    }
}
