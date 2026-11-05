use actix_web::{
    body::{EitherBody, MessageBody},
    dev::{ServiceRequest, ServiceResponse},
    http::header::{HeaderName, HeaderValue},
    http::Method,
    middleware::Next,
    web, Error, HttpResponse,
};
use jsonwebtoken::{decode, decode_header, Algorithm, DecodingKey, Validation};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Clone)]
pub struct AuthConfig {
    pub secret: String,
    pub peer_secret: String,
}

#[derive(Deserialize, Serialize)]
struct Claims {
    sub: Uuid,
    exp: u64,
    #[serde(rename = "type")]
    token_type: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    aud: Option<String>,
}

enum Identity {
    User(Uuid),
    Reindex,
}

fn identity(token: &str, config: &AuthConfig) -> Option<Identity> {
    let header = decode_header(token).ok()?;
    if !matches!(
        header.alg,
        Algorithm::HS256 | Algorithm::HS384 | Algorithm::HS512
    ) {
        return None;
    }
    let mut validation = Validation::new(header.alg);
    validation.set_required_spec_claims(&["exp", "sub"]);
    validation.leeway = 0;
    validation.set_audience(&["file-service:reindex"]);
    for secret in [&config.secret, &config.peer_secret] {
        if secret.is_empty() {
            continue;
        }
        if let Ok(data) = decode::<Claims>(
            token,
            &DecodingKey::from_secret(secret.as_bytes()),
            &validation,
        ) {
            if data.claims.token_type == "access" {
                return Some(Identity::User(data.claims.sub));
            }
            if data.claims.token_type == "service"
                && data.claims.aud.as_deref() == Some("file-service:reindex")
            {
                return Some(Identity::Reindex);
            }
        }
    }
    None
}

pub async fn authenticate(
    mut req: ServiceRequest,
    next: Next<impl MessageBody>,
) -> Result<ServiceResponse<EitherBody<impl MessageBody>>, Error> {
    if matches!(req.path(), "/health" | "/metrics") {
        return Ok(next.call(req).await?.map_into_left_body());
    }
    let identity = req.app_data::<web::Data<AuthConfig>>().and_then(|config| {
        let header = req.headers().get("Authorization")?.to_str().ok()?;
        let (scheme, token) = header.split_once(' ')?;
        if !scheme.eq_ignore_ascii_case("Bearer") {
            return None;
        }
        identity(token, config)
    });
    match identity {
        Some(Identity::User(user_id)) => {
            req.headers_mut().insert(
                HeaderName::from_static("x-user-id"),
                HeaderValue::from_str(&user_id.to_string()).expect("UUID is a valid header value"),
            );
        }
        Some(Identity::Reindex) if req.method() == Method::GET && req.path() == "/api/v1/files" => {
            req.headers_mut().remove("x-user-id");
        }
        _ => {
            return Ok(req
                .into_response(
                    HttpResponse::Unauthorized().json(serde_json::json!({"error": "unauthorized"})),
                )
                .map_into_right_body())
        }
    }
    Ok(next.call(req).await?.map_into_left_body())
}

#[cfg(test)]
mod tests {
    use super::*;
    use actix_web::{middleware::from_fn, test, App, HttpRequest, HttpResponse};
    use jsonwebtoken::{encode, EncodingKey, Header};

    const SECRET: &str = "unit-test-signing-key-not-a-deployment-secret";

    fn token(sub: Uuid, token_type: &str, exp: u64, secret: &str) -> String {
        encode(
            &Header::new(Algorithm::HS384),
            &Claims {
                sub,
                exp,
                token_type: token_type.into(),
                aud: None,
            },
            &EncodingKey::from_secret(secret.as_bytes()),
        )
        .unwrap()
    }

    async fn identity(req: HttpRequest) -> HttpResponse {
        HttpResponse::Ok().body(
            req.headers()
                .get("X-User-ID")
                .map(|h| h.to_str().unwrap())
                .unwrap_or("all")
                .to_owned(),
        )
    }

    #[actix_web::test]
    async fn limits_reindex_credentials_to_read_only_catalog() {
        let app = test::init_service(
            App::new()
                .app_data(web::Data::new(AuthConfig {
                    secret: SECRET.into(),
                    peer_secret: String::new(),
                }))
                .wrap(from_fn(authenticate))
                .route("/api/v1/files", web::get().to(identity)),
        )
        .await;
        let service_token = encode(
            &Header::new(Algorithm::HS256),
            &Claims {
                sub: Uuid::nil(),
                exp: 4102444800,
                token_type: "service".into(),
                aud: Some("file-service:reindex".into()),
            },
            &EncodingKey::from_secret(SECRET.as_bytes()),
        )
        .unwrap();
        let response = test::call_service(
            &app,
            test::TestRequest::get()
                .uri("/api/v1/files")
                .insert_header(("Authorization", format!("Bearer {service_token}")))
                .insert_header(("X-User-ID", Uuid::new_v4().to_string()))
                .to_request(),
        )
        .await;
        assert_eq!(response.status(), 200);
        assert_eq!(test::read_body(response).await, "all");
        for (method, path) in [
            (Method::POST, "/api/v1/files"),
            (Method::GET, "/api/v1/files/shared"),
        ] {
            let response = test::call_service(
                &app,
                test::TestRequest::default()
                    .method(method)
                    .uri(path)
                    .insert_header(("Authorization", format!("Bearer {service_token}")))
                    .to_request(),
            )
            .await;
            assert_eq!(response.status(), 401);
        }
        let response = test::call_service(
            &app,
            test::TestRequest::get()
                .uri("/api/v1/files")
                .insert_header((
                    "Authorization",
                    format!(
                        "Bearer {}",
                        token(Uuid::nil(), "service", 4102444800, SECRET)
                    ),
                ))
                .to_request(),
        )
        .await;
        assert_eq!(response.status(), 401);
    }

    #[actix_web::test]
    async fn authenticates_subject_not_header() {
        let app = test::init_service(
            App::new()
                .app_data(web::Data::new(AuthConfig {
                    secret: SECRET.into(),
                    peer_secret: String::new(),
                }))
                .wrap(from_fn(authenticate))
                .route("/api/v1/files", web::get().to(identity))
                .route(
                    "/health",
                    web::get().to(|| async { HttpResponse::Ok().finish() }),
                )
                .route(
                    "/metrics",
                    web::get().to(|| async { HttpResponse::Ok().finish() }),
                ),
        )
        .await;
        let user = Uuid::new_v4();
        for path in ["/health", "/metrics"] {
            assert_eq!(
                test::call_service(&app, test::TestRequest::get().uri(path).to_request())
                    .await
                    .status(),
                200
            );
        }
        for auth in [
            None,
            Some("Bearer invalid".to_string()),
            Some(format!("Bearer {}", token(user, "access", 1, SECRET))),
            Some(format!(
                "Bearer {}",
                token(user, "refresh", 4102444800, SECRET)
            )),
            Some(format!(
                "Bearer {}",
                token(user, "access", 4102444800, "wrong-key")
            )),
        ] {
            let mut request = test::TestRequest::get()
                .uri("/api/v1/files")
                .insert_header(("X-User-ID", user.to_string()));
            if let Some(value) = auth {
                request = request.insert_header(("Authorization", value));
            }
            assert_eq!(
                test::call_service(&app, request.to_request())
                    .await
                    .status(),
                401
            );
        }
        let request = test::TestRequest::get()
            .uri("/api/v1/files")
            .insert_header(("X-User-ID", Uuid::new_v4().to_string()))
            .insert_header((
                "Authorization",
                format!("Bearer {}", token(user, "access", 4102444800, SECRET)),
            ))
            .to_request();
        let response = test::call_service(&app, request).await;
        assert_eq!(response.status(), 200);
        assert_eq!(test::read_body(response).await, user.to_string());
    }
}
