//! QA unit tests for file-sharing models and error mapping.
//! The crate is binary-only, so the modules under test are included by path.

#[allow(dead_code)]
#[path = "../src/models.rs"]
mod models;

#[allow(dead_code)]
#[path = "../src/errors.rs"]
mod errors;

use actix_web::http::StatusCode;
use actix_web::ResponseError;
use chrono::Utc;
use errors::ServiceError;
use models::{FileDetailResponse, FileMetadata, FileShare, ShareFileRequest, ShareFileResponse, SharePermission};
use serde_json::json;
use uuid::Uuid;

fn sampleShare(permission: SharePermission) -> FileShare {
    FileShare {
        id: Uuid::new_v4(),
        file_id: Uuid::new_v4(),
        shared_with: Uuid::new_v4(),
        permission,
        shared_by: Uuid::new_v4(),
        created_at: Utc::now(),
    }
}

fn sampleFile() -> FileMetadata {
    let now = Utc::now();
    FileMetadata {
        id: Uuid::new_v4(),
        name: "report.pdf".into(),
        mime_type: "application/pdf".into(),
        size_bytes: 42,
        s3_key: "files/report.pdf".into(),
        folder_id: None,
        owner_id: Uuid::new_v4(),
        version: 1,
        is_trashed: false,
        created_at: now,
        updated_at: now,
    }
}

#[test]
fn permissionDisplaysAsLowercaseRole() {
    assert_eq!(SharePermission::Viewer.to_string(), "viewer");
    assert_eq!(SharePermission::Editor.to_string(), "editor");
}

#[test]
fn permissionParsesKnownValuesCaseInsensitively() {
    assert_eq!(SharePermission::from_str_value("viewer"), Some(SharePermission::Viewer));
    assert_eq!(SharePermission::from_str_value("EDITOR"), Some(SharePermission::Editor));
    assert_eq!(SharePermission::from_str_value("Viewer"), Some(SharePermission::Viewer));
}

#[test]
fn permissionRejectsUnknownValues() {
    for bad in ["", "owner", "view", "edit", "admin", "viewer "] {
        assert_eq!(SharePermission::from_str_value(bad), None, "{bad:?} should be rejected");
    }
}

#[test]
fn permissionDisplayRoundTripsThroughParser() {
    for p in [SharePermission::Viewer, SharePermission::Editor] {
        assert_eq!(SharePermission::from_str_value(&p.to_string()), Some(p));
    }
}

#[test]
fn permissionSerializesLowercase() {
    assert_eq!(serde_json::to_value(SharePermission::Viewer).unwrap(), json!("viewer"));
    assert_eq!(serde_json::to_value(SharePermission::Editor).unwrap(), json!("editor"));
}

#[test]
fn permissionDeserializeRejectsFrontendVocabulary() {
    assert!(serde_json::from_value::<SharePermission>(json!("view")).is_err());
    assert!(serde_json::from_value::<SharePermission>(json!("edit")).is_err());
    assert!(serde_json::from_value::<SharePermission>(json!("Viewer")).is_err());
}

#[test]
fn shareRequestDeserializesSnakeCasePayload() {
    let sharedWith = Uuid::new_v4();
    let sharedBy = Uuid::new_v4();
    let req: ShareFileRequest = serde_json::from_value(json!({
        "shared_with": sharedWith,
        "permission": "editor",
        "shared_by": sharedBy,
    }))
    .unwrap();
    assert_eq!(req.shared_with, sharedWith);
    assert_eq!(req.shared_by, sharedBy);
    assert_eq!(req.permission, SharePermission::Editor);
}

#[test]
fn shareRequestRejectsMissingOrInvalidFields() {
    let uid = Uuid::new_v4();
    assert!(serde_json::from_value::<ShareFileRequest>(json!({"permission": "viewer", "shared_by": uid})).is_err());
    assert!(serde_json::from_value::<ShareFileRequest>(json!({"shared_with": uid, "shared_by": uid})).is_err());
    assert!(serde_json::from_value::<ShareFileRequest>(json!({"shared_with": "not-a-uuid", "permission": "viewer", "shared_by": uid})).is_err());
    assert!(serde_json::from_value::<ShareFileRequest>(json!({"shared_with": uid, "permission": "owner", "shared_by": uid})).is_err());
}

#[test]
fn shareRoundTripsThroughJson() {
    let share = sampleShare(SharePermission::Viewer);
    let value = serde_json::to_value(&share).unwrap();
    assert_eq!(value["permission"], "viewer");
    assert_eq!(value["shared_with"], share.shared_with.to_string());
    let back: FileShare = serde_json::from_value(value).unwrap();
    assert_eq!(back.id, share.id);
    assert_eq!(back.permission, SharePermission::Viewer);
}

#[test]
fn shareResponseWrapsShareUnderShareKey() {
    let share = sampleShare(SharePermission::Editor);
    let value = serde_json::to_value(ShareFileResponse { share: share.clone() }).unwrap();
    assert_eq!(value["share"]["id"], share.id.to_string());
    assert_eq!(value["share"]["permission"], "editor");
}

#[test]
fn fileDetailFlattensFileAndListsShares() {
    let file = sampleFile();
    let shares = vec![sampleShare(SharePermission::Viewer), sampleShare(SharePermission::Editor)];
    let value = serde_json::to_value(FileDetailResponse { file: file.clone(), shared_with: shares }).unwrap();
    assert_eq!(value["id"], file.id.to_string());
    assert_eq!(value["owner_id"], file.owner_id.to_string());
    assert!(value.get("file").is_none(), "file metadata must be flattened");
    assert_eq!(value["shared_with"].as_array().unwrap().len(), 2);
}

#[test]
fn fileDetailWithNoSharesEmitsEmptyArray() {
    let value = serde_json::to_value(FileDetailResponse { file: sampleFile(), shared_with: vec![] }).unwrap();
    assert_eq!(value["shared_with"], json!([]));
}

#[test]
fn shareNotFoundMapsTo404() {
    let err = ServiceError::ShareNotFound("Share not found".into());
    assert_eq!(err.error_response().status(), StatusCode::NOT_FOUND);
}

#[test]
fn forbiddenMapsTo403() {
    let err = ServiceError::Forbidden("not owner".into());
    assert_eq!(err.error_response().status(), StatusCode::FORBIDDEN);
}

#[test]
fn unauthorizedMapsTo401() {
    assert_eq!(
        ServiceError::Unauthorized("x".into()).error_response().status(),
        StatusCode::UNAUTHORIZED
    );
}

#[test]
fn badRequestMapsTo400() {
    assert_eq!(
        ServiceError::BadRequest("invalid file id".into()).error_response().status(),
        StatusCode::BAD_REQUEST
    );
}

#[test]
fn fileNotFoundMapsTo404() {
    assert_eq!(
        ServiceError::FileNotFound("x".into()).error_response().status(),
        StatusCode::NOT_FOUND
    );
}
