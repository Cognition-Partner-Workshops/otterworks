use actix_web::dev::Payload;
use actix_web::{FromRequest, HttpRequest};
use futures_util::future::{ready, Ready};
use uuid::Uuid;

use crate::errors::ServiceError;

/// Header the api-gateway sets from the verified JWT subject.
pub const USER_ID_HEADER: &str = "X-User-ID";

/// Identity of the authenticated caller, taken from `X-User-ID`.
///
/// Every by-id handler takes this extractor, so a request without a
/// parseable caller id is rejected with 401 before any record is touched.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CallerId(pub Uuid);

pub fn caller_id_from_request(req: &HttpRequest) -> Result<CallerId, ServiceError> {
    req.headers()
        .get(USER_ID_HEADER)
        .and_then(|v| v.to_str().ok())
        .and_then(|s| s.trim().parse::<Uuid>().ok())
        .map(CallerId)
        .ok_or_else(|| ServiceError::Unauthorized("missing or invalid X-User-ID header".into()))
}

impl FromRequest for CallerId {
    type Error = ServiceError;
    type Future = Ready<Result<Self, Self::Error>>;

    fn from_request(req: &HttpRequest, _payload: &mut Payload) -> Self::Future {
        ready(caller_id_from_request(req))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use actix_web::test::TestRequest;

    #[actix_rt::test]
    async fn extracts_caller_from_header() {
        let user_id = Uuid::new_v4();
        let req = TestRequest::default()
            .insert_header((USER_ID_HEADER, user_id.to_string()))
            .to_http_request();
        let caller = CallerId::extract(&req).await.unwrap();
        assert_eq!(caller, CallerId(user_id));
    }

    #[actix_rt::test]
    async fn rejects_missing_header() {
        let req = TestRequest::default().to_http_request();
        let err = CallerId::extract(&req).await.unwrap_err();
        assert!(matches!(err, ServiceError::Unauthorized(_)));
    }

    #[actix_rt::test]
    async fn rejects_non_uuid_header() {
        let req = TestRequest::default()
            .insert_header((USER_ID_HEADER, "not-a-uuid"))
            .to_http_request();
        let err = CallerId::extract(&req).await.unwrap_err();
        assert!(matches!(err, ServiceError::Unauthorized(_)));
    }
}
