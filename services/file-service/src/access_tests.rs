use crate::{handlers, metadata::MetadataClient};
use actix_web::{http::StatusCode, test, web, App, HttpRequest, HttpResponse, HttpServer};
use aws_sdk_dynamodb::config::{Credentials, Region};

const OWNER: &str = "00000000-0000-0000-0000-000000000001";
const OTHER: &str = "00000000-0000-0000-0000-000000000002";
const FILE: &str = "00000000-0000-0000-0000-000000000003";

async fn check_access(user: Option<&str>, expected: StatusCode, shared: bool) {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let endpoint = format!("http://{}", listener.local_addr().unwrap());
    let server = HttpServer::new(move || App::new().default_service(web::to(move |req: HttpRequest, body: web::Bytes| async move {
        let body: serde_json::Value = serde_json::from_slice(&body).unwrap();
        if req.headers().get("x-amz-target").unwrap().to_str().unwrap().ends_with("GetItem") {
            HttpResponse::Ok().json(serde_json::json!({"Item": {
                "id": {"S": FILE}, "owner_id": {"S": OWNER}, "name": {"S": "private"},
                "mime_type": {"S": "text/plain"}, "size_bytes": {"N": "1"}, "s3_key": {"S": "private"},
                "version": {"N": "1"}, "is_trashed": {"BOOL": false},
                "created_at": {"S": "2026-01-01T00:00:00Z"}, "updated_at": {"S": "2026-01-01T00:00:00Z"}
            }}))
        } else if shared && body["TableName"] == "shares" {
            HttpResponse::Ok().json(serde_json::json!({"Items": [{
                "id": {"S": FILE}, "file_id": {"S": FILE}, "shared_with": {"S": OTHER},
                "permission": {"S": "viewer"}, "shared_by": {"S": OWNER},
                "created_at": {"S": "2026-01-01T00:00:00Z"}
            }]}))
        } else {
            HttpResponse::Ok().json(serde_json::json!({"Items": []}))
        }
    }))).listen(listener).unwrap().run();
    let handle = server.handle();
    actix_rt::spawn(server);
    let config = aws_sdk_dynamodb::config::Builder::new()
        .behavior_version_latest()
        .region(Region::new("us-east-1"))
        .credentials_provider(Credentials::new("test", "test", None, None, "test"))
        .endpoint_url(endpoint)
        .build();
    let meta = MetadataClient {
        client: aws_sdk_dynamodb::Client::from_conf(config),
        files_table: "files".into(),
        folders_table: "folders".into(),
        versions_table: "versions".into(),
        shares_table: "shares".into(),
    };
    let app = test::init_service(
        App::new()
            .app_data(web::Data::new(meta))
            .route("/files/{id}", web::get().to(handlers::get_file_metadata))
            .route(
                "/files/{id}/versions",
                web::get().to(handlers::list_versions),
            )
            .route(
                "/files/{id}/share/{user}",
                web::delete().to(handlers::remove_share),
            )
            .route("/folders/{id}", web::get().to(handlers::get_folder))
            .route("/folders/{id}", web::put().to(handlers::update_folder))
            .route("/folders/{id}", web::delete().to(handlers::delete_folder))
            .route("/folders", web::post().to(handlers::create_folder)),
    )
    .await;
    for kind in ["files", "folders"] {
        let mut request = test::TestRequest::get().uri(&format!("/{kind}/{FILE}"));
        if let Some(user) = user {
            request = request.insert_header(("X-User-ID", user));
        }
        let response = test::call_service(&app, request.to_request()).await;
        let expected = if shared && kind == "files" {
            StatusCode::OK
        } else {
            expected
        };
        assert_eq!(
            response.status(),
            expected,
            "{kind}: unexpected access result"
        );
    }
    if user != Some(OWNER) {
        for (method, path) in [
            (actix_web::http::Method::PUT, format!("/folders/{FILE}")),
            (actix_web::http::Method::DELETE, format!("/folders/{FILE}")),
            (
                actix_web::http::Method::DELETE,
                format!("/files/{FILE}/share/{OTHER}"),
            ),
        ] {
            let mut request = test::TestRequest::default()
                .method(method)
                .uri(&path)
                .set_json(serde_json::json!({"name": "changed"}));
            if let Some(user) = user {
                request = request.insert_header(("X-User-ID", user));
            }
            assert_eq!(
                test::call_service(&app, request.to_request())
                    .await
                    .status(),
                expected,
                "{path}"
            );
        }
    } else {
        let request = test::TestRequest::post()
            .uri("/folders")
            .insert_header(("X-User-ID", OWNER))
            .set_json(serde_json::json!({"name": "owned", "owner_id": OTHER}))
            .to_request();
        let folder: serde_json::Value = test::call_and_read_body_json(&app, request).await;
        assert_eq!(
            folder["owner_id"], OWNER,
            "body identity must not select the owner"
        );
    }
    let mut request = test::TestRequest::get().uri(&format!("/files/{FILE}/versions"));
    if let Some(user) = user {
        request = request.insert_header(("X-User-ID", user));
    }
    assert_eq!(
        test::call_service(&app, request.to_request())
            .await
            .status(),
        if shared { StatusCode::OK } else { expected }
    );
    handle.stop(true).await;
}

#[actix_rt::test]
async fn anonymous_cannot_read_files_or_folders() {
    check_access(None, StatusCode::UNAUTHORIZED, false).await;
}

#[actix_rt::test]
async fn non_owner_cannot_read_files_or_folders() {
    check_access(Some(OTHER), StatusCode::NOT_FOUND, false).await;
}

#[actix_rt::test]
async fn owner_can_read_files_and_folders() {
    check_access(Some(OWNER), StatusCode::OK, false).await;
}

#[actix_rt::test]
async fn shared_reader_can_read_but_not_mutate() {
    check_access(Some(OTHER), StatusCode::NOT_FOUND, true).await;
}
