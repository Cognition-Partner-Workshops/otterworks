use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

// ── File Metadata ──────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileMetadata {
    pub id: Uuid,
    pub name: String,
    pub mime_type: String,
    pub size_bytes: u64,
    pub s3_key: String,
    pub folder_id: Option<Uuid>,
    pub owner_id: Uuid,
    pub version: u32,
    pub is_trashed: bool,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Serialize)]
pub struct FileDetailResponse {
    #[serde(flatten)]
    pub file: FileMetadata,
    pub shared_with: Vec<FileShare>,
}

// ── Folder ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Folder {
    pub id: Uuid,
    pub name: String,
    pub parent_id: Option<Uuid>,
    pub owner_id: Uuid,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

// ── File Version ───────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileVersion {
    pub file_id: Uuid,
    pub version: u32,
    pub s3_key: String,
    pub size_bytes: u64,
    pub created_by: Uuid,
    pub created_at: DateTime<Utc>,
}

// ── File Share ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileShare {
    pub id: Uuid,
    pub file_id: Uuid,
    pub shared_with: Uuid,
    pub permission: SharePermission,
    pub shared_by: Uuid,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum SharePermission {
    Viewer,
    Editor,
}

impl std::fmt::Display for SharePermission {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SharePermission::Viewer => write!(f, "viewer"),
            SharePermission::Editor => write!(f, "editor"),
        }
    }
}

impl SharePermission {
    pub fn from_str_value(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "viewer" => Some(SharePermission::Viewer),
            "editor" => Some(SharePermission::Editor),
            _ => None,
        }
    }
}

// ── Request / Response Types ───────────────────────────────────────────

#[derive(Debug, Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub service: String,
    pub version: String,
}

#[derive(Debug, Serialize)]
pub struct UploadResponse {
    pub file: FileMetadata,
}

#[derive(Debug, Serialize)]
pub struct DownloadResponse {
    pub url: String,
    pub expires_in_secs: u64,
}

#[derive(Debug, Deserialize)]
pub struct ListFilesQuery {
    pub folder_id: Option<Uuid>,
    pub owner_id: Option<Uuid>,
    pub page: Option<u32>,
    pub page_size: Option<u32>,
    pub include_trashed: Option<bool>,
}

#[derive(Debug, Serialize)]
pub struct ListFilesResponse {
    pub files: Vec<FileMetadata>,
    pub total: usize,
    pub page: u32,
    pub page_size: u32,
}

#[derive(Debug, Serialize)]
pub struct ListVersionsResponse {
    pub versions: Vec<FileVersion>,
}

#[derive(Debug, Deserialize)]
pub struct ListFoldersQuery {
    pub parent_id: Option<Uuid>,
    pub owner_id: Option<Uuid>,
}

#[derive(Debug, Serialize)]
pub struct ListFoldersResponse {
    pub folders: Vec<Folder>,
}

#[derive(Debug, Deserialize)]
pub struct CreateFolderRequest {
    pub name: String,
    pub parent_id: Option<Uuid>,
    pub owner_id: Uuid,
}

#[derive(Debug, Deserialize)]
pub struct UpdateFolderRequest {
    pub name: Option<String>,
    pub parent_id: Option<Uuid>,
}

#[derive(Debug, Deserialize)]
pub struct MoveFileRequest {
    pub folder_id: Option<Uuid>,
}

#[derive(Debug, Deserialize)]
pub struct RenameFileRequest {
    pub name: String,
}

#[derive(Debug, Deserialize)]
pub struct ShareFileRequest {
    pub shared_with: Uuid,
    pub permission: SharePermission,
    pub shared_by: Uuid,
}

#[derive(Debug, Serialize)]
pub struct ShareFileResponse {
    pub share: FileShare,
}

// ── Activity ───────────────────────────────────────────────────────────

#[derive(Debug, Serialize)]
pub struct ActivityItem {
    pub id: String,
    #[serde(rename = "type")]
    pub activity_type: String,
    pub description: String,
    pub actor_name: String,
    pub resource_name: String,
    pub resource_type: String,
    pub resource_id: String,
    pub created_at: String,
}

#[derive(Debug, Deserialize)]
pub struct ActivityQuery {
    pub limit: Option<u32>,
}

#[derive(Debug, Serialize)]
pub struct ActivityResponse {
    pub items: Vec<ActivityItem>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use actix_web::web;
    use serde_json::json;

    fn sample_file() -> FileMetadata {
        let ts = DateTime::parse_from_rfc3339("2024-05-01T12:00:00+00:00")
            .unwrap()
            .with_timezone(&Utc);
        FileMetadata {
            id: Uuid::nil(),
            name: "report.pdf".into(),
            mime_type: "application/pdf".into(),
            size_bytes: 2048,
            s3_key: "files/o/f".into(),
            folder_id: None,
            owner_id: Uuid::nil(),
            version: 1,
            is_trashed: false,
            created_at: ts,
            updated_at: ts,
        }
    }

    #[test]
    fn share_permission_display_is_lowercase() {
        assert_eq!(SharePermission::Viewer.to_string(), "viewer");
        assert_eq!(SharePermission::Editor.to_string(), "editor");
    }

    #[test]
    fn share_permission_from_str_is_case_insensitive() {
        assert_eq!(
            SharePermission::from_str_value("VIEWER"),
            Some(SharePermission::Viewer)
        );
        assert_eq!(
            SharePermission::from_str_value("eDiToR"),
            Some(SharePermission::Editor)
        );
        assert_eq!(SharePermission::from_str_value(""), None);
        assert_eq!(SharePermission::from_str_value("owner"), None);
        assert_eq!(SharePermission::from_str_value(" viewer"), None);
    }

    #[test]
    fn share_permission_display_round_trips_through_from_str() {
        for p in [SharePermission::Viewer, SharePermission::Editor] {
            assert_eq!(SharePermission::from_str_value(&p.to_string()), Some(p));
        }
    }

    #[test]
    fn share_permission_serde_uses_lowercase() {
        assert_eq!(
            serde_json::to_value(SharePermission::Editor).unwrap(),
            json!("editor")
        );
        let p: SharePermission = serde_json::from_value(json!("viewer")).unwrap();
        assert_eq!(p, SharePermission::Viewer);
        assert!(serde_json::from_value::<SharePermission>(json!("owner")).is_err());
    }

    #[test]
    fn file_metadata_round_trips_through_json() {
        let file = sample_file();
        let value = serde_json::to_value(&file).unwrap();
        assert_eq!(value["name"], "report.pdf");
        assert_eq!(value["size_bytes"], 2048);
        assert_eq!(value["folder_id"], serde_json::Value::Null);
        let back: FileMetadata = serde_json::from_value(value).unwrap();
        assert_eq!(back.id, file.id);
        assert_eq!(back.created_at, file.created_at);
    }

    #[test]
    fn file_detail_response_flattens_file_fields() {
        let resp = FileDetailResponse {
            file: sample_file(),
            shared_with: vec![],
        };
        let value = serde_json::to_value(&resp).unwrap();
        assert_eq!(value["name"], "report.pdf");
        assert_eq!(value["mime_type"], "application/pdf");
        assert_eq!(value["shared_with"], json!([]));
        assert!(value.get("file").is_none());
    }

    #[test]
    fn activity_item_serializes_type_field() {
        let item = ActivityItem {
            id: "upload-1".into(),
            activity_type: "upload".into(),
            description: "Uploaded a".into(),
            actor_name: "You".into(),
            resource_name: "a".into(),
            resource_type: "file".into(),
            resource_id: "1".into(),
            created_at: "2024-01-01T00:00:00+00:00".into(),
        };
        let value = serde_json::to_value(&item).unwrap();
        assert_eq!(value["type"], "upload");
        assert!(value.get("activity_type").is_none());
    }

    #[test]
    fn list_files_query_parses_all_fields() {
        let folder = Uuid::new_v4();
        let owner = Uuid::new_v4();
        let q = web::Query::<ListFilesQuery>::from_query(&format!(
            "folder_id={folder}&owner_id={owner}&page=3&page_size=25&include_trashed=true"
        ))
        .unwrap();
        assert_eq!(q.folder_id, Some(folder));
        assert_eq!(q.owner_id, Some(owner));
        assert_eq!(q.page, Some(3));
        assert_eq!(q.page_size, Some(25));
        assert_eq!(q.include_trashed, Some(true));
    }

    #[test]
    fn list_files_query_fields_are_optional() {
        let q = web::Query::<ListFilesQuery>::from_query("").unwrap();
        assert!(q.folder_id.is_none());
        assert!(q.owner_id.is_none());
        assert!(q.page.is_none());
        assert!(q.page_size.is_none());
        assert!(q.include_trashed.is_none());
    }

    #[test]
    fn list_files_query_rejects_invalid_values() {
        assert!(web::Query::<ListFilesQuery>::from_query("folder_id=not-a-uuid").is_err());
        assert!(web::Query::<ListFilesQuery>::from_query("page=-1").is_err());
        assert!(web::Query::<ListFilesQuery>::from_query("include_trashed=maybe").is_err());
    }

    #[test]
    fn create_folder_request_requires_name_and_owner() {
        let owner = Uuid::new_v4();
        let req: CreateFolderRequest =
            serde_json::from_value(json!({"name": "Docs", "owner_id": owner})).unwrap();
        assert_eq!(req.name, "Docs");
        assert_eq!(req.owner_id, owner);
        assert!(req.parent_id.is_none());
        assert!(serde_json::from_value::<CreateFolderRequest>(json!({"name": "Docs"})).is_err());
        assert!(serde_json::from_value::<CreateFolderRequest>(json!({"owner_id": owner})).is_err());
    }

    #[test]
    fn share_file_request_parses_permission() {
        let a = Uuid::new_v4();
        let b = Uuid::new_v4();
        let req: ShareFileRequest = serde_json::from_value(
            json!({"shared_with": a, "permission": "editor", "shared_by": b}),
        )
        .unwrap();
        assert_eq!(req.permission, SharePermission::Editor);
        assert!(serde_json::from_value::<ShareFileRequest>(
            json!({"shared_with": a, "permission": "admin", "shared_by": b})
        )
        .is_err());
    }

    #[test]
    fn move_and_update_requests_allow_missing_fields() {
        let m: MoveFileRequest = serde_json::from_value(json!({})).unwrap();
        assert!(m.folder_id.is_none());
        let u: UpdateFolderRequest = serde_json::from_value(json!({})).unwrap();
        assert!(u.name.is_none());
        assert!(u.parent_id.is_none());
        let r: RenameFileRequest = serde_json::from_value(json!({"name": "x"})).unwrap();
        assert_eq!(r.name, "x");
    }

    #[test]
    fn activity_query_limit_is_optional() {
        assert!(web::Query::<ActivityQuery>::from_query("")
            .unwrap()
            .limit
            .is_none());
        assert_eq!(
            web::Query::<ActivityQuery>::from_query("limit=5")
                .unwrap()
                .limit,
            Some(5)
        );
    }
}
