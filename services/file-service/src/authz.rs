//! Object-level authorization for files and folders.
//!
//! The api-gateway authenticates the JWT and forwards the subject as
//! `X-User-ID`. A request without that header comes from an in-cluster
//! service (search-service reindex, admin-service probes) and keeps the
//! pre-existing trusted behavior.

use actix_web::HttpRequest;
use uuid::Uuid;

use crate::errors::ServiceError;
use crate::models::SharePermission;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Caller {
    Internal,
    User(Uuid),
}

impl Caller {
    pub fn from_request(req: &HttpRequest) -> Result<Self, ServiceError> {
        match req.headers().get("X-User-ID") {
            None => Ok(Caller::Internal),
            Some(value) => value
                .to_str()
                .ok()
                .and_then(|s| s.trim().parse::<Uuid>().ok())
                .map(Caller::User)
                .ok_or_else(|| ServiceError::Unauthorized("invalid user identity".into())),
        }
    }

    pub fn user_id(&self) -> Option<Uuid> {
        match self {
            Caller::Internal => None,
            Caller::User(id) => Some(*id),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FileAccess {
    /// Metadata, download, versions: owner, viewer or editor.
    Read,
    /// Rename: owner or editor.
    Write,
    /// Move, trash, restore, delete, share: owner only.
    Owner,
}

/// Decide whether `caller` may perform `need` on a file owned by `owner`.
///
/// `share` is the caller's share on that file, if any. Callers with no
/// relationship to the file get `FileNotFound` so the id's existence is not
/// revealed; share recipients without enough permission get `Forbidden`.
pub fn check_file_access(
    owner: Uuid,
    caller: Caller,
    share: Option<&SharePermission>,
    need: FileAccess,
    file_id: &Uuid,
) -> Result<(), ServiceError> {
    let caller_id = match caller {
        Caller::Internal => return Ok(()),
        Caller::User(id) => id,
    };
    if caller_id == owner {
        return Ok(());
    }
    let allowed = match (share, need) {
        (None, _) => return Err(ServiceError::FileNotFound(file_id.to_string())),
        (Some(_), FileAccess::Read) => true,
        (Some(SharePermission::Editor), FileAccess::Write) => true,
        _ => false,
    };
    if allowed {
        Ok(())
    } else {
        Err(ServiceError::Forbidden(format!(
            "insufficient permission on file {file_id}"
        )))
    }
}

/// Folders are not shareable: only the owner (or an internal caller) may use one.
pub fn check_folder_access(
    folder_owner: Uuid,
    caller: Caller,
    folder_id: &Uuid,
) -> Result<(), ServiceError> {
    match caller {
        Caller::User(id) if id != folder_owner => {
            Err(ServiceError::FolderNotFound(folder_id.to_string()))
        }
        _ => Ok(()),
    }
}

/// A file or sub-folder may only be placed in a folder owned by the same user.
pub fn check_folder_target(
    folder_owner: Uuid,
    item_owner: Uuid,
    folder_id: &Uuid,
) -> Result<(), ServiceError> {
    if folder_owner == item_owner {
        Ok(())
    } else {
        Err(ServiceError::FolderNotFound(folder_id.to_string()))
    }
}

/// Who may revoke a share: the file owner, or the recipient removing their own.
pub fn check_share_revoke(
    owner: Uuid,
    caller: Caller,
    caller_share: Option<&SharePermission>,
    target_user: &Uuid,
    file_id: &Uuid,
) -> Result<(), ServiceError> {
    match caller {
        Caller::User(id) if id == *target_user => Ok(()),
        _ => check_file_access(owner, caller, caller_share, FileAccess::Owner, file_id),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use actix_web::http::StatusCode;
    use actix_web::test::TestRequest;
    use actix_web::ResponseError;

    fn status(result: Result<(), ServiceError>) -> Option<StatusCode> {
        result.err().map(|e| e.error_response().status())
    }

    #[test]
    fn caller_is_internal_without_identity_header() {
        let req = TestRequest::default().to_http_request();
        assert_eq!(Caller::from_request(&req).unwrap(), Caller::Internal);
    }

    #[test]
    fn caller_is_user_from_identity_header() {
        let id = Uuid::new_v4();
        let req = TestRequest::default()
            .insert_header(("X-User-ID", id.to_string()))
            .to_http_request();
        assert_eq!(Caller::from_request(&req).unwrap(), Caller::User(id));
    }

    #[test]
    fn malformed_identity_header_is_rejected_not_treated_as_internal() {
        let req = TestRequest::default()
            .insert_header(("X-User-ID", "not-a-uuid"))
            .to_http_request();
        let err = Caller::from_request(&req).unwrap_err();
        assert_eq!(err.error_response().status(), StatusCode::UNAUTHORIZED);
    }

    #[test]
    fn owner_has_every_access_level() {
        let owner = Uuid::new_v4();
        let file = Uuid::new_v4();
        for need in [FileAccess::Read, FileAccess::Write, FileAccess::Owner] {
            assert!(check_file_access(owner, Caller::User(owner), None, need, &file).is_ok());
        }
    }

    #[test]
    fn internal_caller_keeps_trusted_access() {
        let file = Uuid::new_v4();
        for need in [FileAccess::Read, FileAccess::Write, FileAccess::Owner] {
            assert!(check_file_access(Uuid::new_v4(), Caller::Internal, None, need, &file).is_ok());
        }
    }

    #[test]
    fn stranger_gets_404_for_every_access_level() {
        let file = Uuid::new_v4();
        let stranger = Caller::User(Uuid::new_v4());
        for need in [FileAccess::Read, FileAccess::Write, FileAccess::Owner] {
            assert_eq!(
                status(check_file_access(
                    Uuid::new_v4(),
                    stranger,
                    None,
                    need,
                    &file
                )),
                Some(StatusCode::NOT_FOUND)
            );
        }
    }

    #[test]
    fn viewer_may_read_but_not_write_or_manage() {
        let file = Uuid::new_v4();
        let owner = Uuid::new_v4();
        let viewer = Caller::User(Uuid::new_v4());
        let perm = SharePermission::Viewer;
        assert!(check_file_access(owner, viewer, Some(&perm), FileAccess::Read, &file).is_ok());
        assert_eq!(
            status(check_file_access(
                owner,
                viewer,
                Some(&perm),
                FileAccess::Write,
                &file
            )),
            Some(StatusCode::FORBIDDEN)
        );
        assert_eq!(
            status(check_file_access(
                owner,
                viewer,
                Some(&perm),
                FileAccess::Owner,
                &file
            )),
            Some(StatusCode::FORBIDDEN)
        );
    }

    #[test]
    fn editor_may_read_and_write_but_not_manage() {
        let file = Uuid::new_v4();
        let owner = Uuid::new_v4();
        let editor = Caller::User(Uuid::new_v4());
        let perm = SharePermission::Editor;
        assert!(check_file_access(owner, editor, Some(&perm), FileAccess::Read, &file).is_ok());
        assert!(check_file_access(owner, editor, Some(&perm), FileAccess::Write, &file).is_ok());
        assert_eq!(
            status(check_file_access(
                owner,
                editor,
                Some(&perm),
                FileAccess::Owner,
                &file
            )),
            Some(StatusCode::FORBIDDEN)
        );
    }

    #[test]
    fn folder_access_is_owner_only() {
        let owner = Uuid::new_v4();
        let folder = Uuid::new_v4();
        assert!(check_folder_access(owner, Caller::User(owner), &folder).is_ok());
        assert!(check_folder_access(owner, Caller::Internal, &folder).is_ok());
        assert_eq!(
            status(check_folder_access(
                owner,
                Caller::User(Uuid::new_v4()),
                &folder
            )),
            Some(StatusCode::NOT_FOUND)
        );
    }

    #[test]
    fn folder_target_must_belong_to_item_owner() {
        let owner = Uuid::new_v4();
        let folder = Uuid::new_v4();
        assert!(check_folder_target(owner, owner, &folder).is_ok());
        assert_eq!(
            status(check_folder_target(Uuid::new_v4(), owner, &folder)),
            Some(StatusCode::NOT_FOUND)
        );
    }

    #[test]
    fn owner_may_revoke_any_share() {
        let owner = Uuid::new_v4();
        let file = Uuid::new_v4();
        assert!(
            check_share_revoke(owner, Caller::User(owner), None, &Uuid::new_v4(), &file).is_ok()
        );
    }

    #[test]
    fn recipient_may_remove_own_share() {
        let recipient = Uuid::new_v4();
        let file = Uuid::new_v4();
        let perm = SharePermission::Viewer;
        assert!(check_share_revoke(
            Uuid::new_v4(),
            Caller::User(recipient),
            Some(&perm),
            &recipient,
            &file
        )
        .is_ok());
    }

    #[test]
    fn stranger_and_other_recipients_cannot_revoke_a_share() {
        let owner = Uuid::new_v4();
        let file = Uuid::new_v4();
        let target = Uuid::new_v4();
        assert_eq!(
            status(check_share_revoke(
                owner,
                Caller::User(Uuid::new_v4()),
                None,
                &target,
                &file
            )),
            Some(StatusCode::NOT_FOUND)
        );
        let perm = SharePermission::Editor;
        assert_eq!(
            status(check_share_revoke(
                owner,
                Caller::User(Uuid::new_v4()),
                Some(&perm),
                &target,
                &file
            )),
            Some(StatusCode::FORBIDDEN)
        );
    }
}
