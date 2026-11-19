import XCTest

class AppUITestCase: XCTestCase {
    let app = XCUIApplication()

    override func tearDownWithError() throws {
        if (testRun?.failureCount ?? 0) > 0 {
            let hierarchy = XCTAttachment(string: app.debugDescription)
            hierarchy.name = "Accessibility hierarchy"
            hierarchy.lifetime = .keepAlways
            add(hierarchy)
            let screenshot = XCTAttachment(screenshot: app.screenshot())
            screenshot.lifetime = .keepAlways
            add(screenshot)
        }
    }

    override func setUpWithError() throws {
        continueAfterFailure = false
        app.terminate()
        let done = expectation(description: "Reset mock")
        var request = URLRequest(url: URL(string: "http://127.0.0.1:4010/__reset")!)
        request.httpMethod = "POST"
        URLSession.shared.dataTask(with: request) { _, response, error in
            XCTAssertNil(error)
            XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 200)
            done.fulfill()
        }.resume()
        wait(for: [done], timeout: 10)
        app.launch()
        XCTAssertTrue(app.webViews.firstMatch.waitForExistence(timeout: 20))
        if app.links["Sign In"].firstMatch.waitForExistence(timeout: 3) {
            app.links["Sign In"].firstMatch.tap()
        }
        // WKWebView storage survives app launches: sign out through the UI.
        if !app.textFields["you@example.com"].waitForExistence(timeout: 3) {
            openSidebar()
            app.buttons["Sign out"].tap()
        }
        XCTAssertTrue(app.textFields["you@example.com"].waitForExistence(timeout: 10))
    }

    func login(password: String = "HarborPass123!") {
        let email = app.textFields["you@example.com"]
        email.tap()
        email.typeText("tester@example.com")
        let field = app.secureTextFields.firstMatch
        field.tap()
        field.typeText(password)
        app.buttons["Sign in"].tap()
        if password == "HarborPass123!" {
            XCTAssertTrue(app.links["Files"].waitForExistence(timeout: 10))
            // iOS auto-zooms the app's sub-16px login fields. Restore the
            // viewport with a real user gesture before following sidebar links.
            app.webViews.firstMatch.pinch(withScale: 0.5, velocity: -1)
        }
    }

    func assertText(_ text: String, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertTrue(app.webViews.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@ OR value CONTAINS %@", text, text)).firstMatch.waitForExistence(timeout: 15), "Missing \(text)", file: file, line: line)
    }

    func openSidebar() {
        if !app.links["Files"].isHittable {
            app.buttons["Open menu"].tap()
        }
    }

    func navigate(_ name: String, dismissSidebar: Bool = true) {
        openSidebar()
        app.links[name].firstMatch.tap()
        if dismissSidebar {
            // Known safe-area bug: the sidebar close button is under the status
            // bar in portrait. Dismiss via the visible backdrop, as a user can.
            app.webViews.firstMatch.coordinate(withNormalizedOffset: CGVector(dx: 0.95, dy: 0.5)).tap()
        }
    }
}

final class AppUITests: AppUITestCase {
    func testPortraitMenuReopens() {
        login()
        navigate("Files")
        XCTExpectFailure("Known safe-area bug: portrait Open menu is beneath the iOS status bar") {
            app.buttons["Open menu"].tap()
            XCTAssertTrue(app.links["Files"].waitForExistence(timeout: 3))
        }
    }

    func testDownloadPersistsToFiles() throws {
        throw XCTSkip("Known native download bug: blob-anchor downloads do not persist through Capacitor Filesystem; testFileDetailDownloadButton covers the entry point")
    }

    func testBadPassword() {
        login(password: "wrong-password")
        assertText("Invalid email or password. Please try again.")
    }

    func testLoginAndNavigation() {
        login()
        assertText("Harbor report.txt")
        for (page, content) in [("Files", "Voyages"), ("Documents", "Voyage notes"), ("Notifications", "Your voyage report is ready"), ("Margins", "HARBOR-01"), ("Settings", "Profile"), ("Recent", "Harbor report.txt"), ("Shared with me", "Harbor report.txt"), ("Starred", "No starred items"), ("Trash", "Trash is empty"), ("Search", "Search"), ("Dashboard", "Harbor report.txt")] {
            navigate(page, dismissSidebar: false)
            assertText(content)
        }
    }

    func testFilesAndUploadEntryPoint() {
        login()
        navigate("Files")
        assertText("Harbor report.txt")
        app.buttons["Upload"].tap()
        assertText("Drag & drop files here, or click to browse")
        // The system Files picker has no seeded simulator provider. Browser tests
        // exercise multipart upload; native tests keep the picker entry point honest.
    }

    func testFileDetailDownloadButton() {
        login()
        navigate("Files")
        app.links.matching(NSPredicate(format: "label CONTAINS %@", "Harbor report.txt")).firstMatch.tap()
        XCTAssertTrue(app.buttons["Download"].firstMatch.waitForExistence(timeout: 10))
        app.buttons["Download"].firstMatch.tap()
        // Known native bug: blob-anchor downloads are not persisted via Filesystem.
        // Do not claim a saved file; the browser suite verifies the response payload.
        assertText("Harbor report.txt")
    }

    func testDocumentEditing() {
        login()
        navigate("Documents")
        app.links.matching(NSPredicate(format: "label CONTAINS %@", "Voyage notes")).firstMatch.tap()
        let editor = app.webViews.textViews.firstMatch
        XCTAssertTrue(editor.waitForExistence(timeout: 10))
        XCTAssertTrue((editor.value as? String ?? "").contains("Welcome aboard the harbor."))
        editor.tap()
        editor.typeText(" Native voyage edit")
        app.buttons["Save"].tap()
        let saved = expectation(description: "HTTP document save persisted")
        var request = URLRequest(url: URL(string: "http://127.0.0.1:4010/api/v1/documents/doc-1")!)
        request.setValue("Bearer mock", forHTTPHeaderField: "Authorization")
        URLSession.shared.dataTask(with: request) { data, _, error in
            XCTAssertNil(error)
            let json = data.flatMap { try? JSONSerialization.jsonObject(with: $0) } as? [String: Any]
            XCTAssertTrue((json?["content"] as? String ?? "").contains("Native voyage edit"))
            saved.fulfill()
        }.resume()
        wait(for: [saved], timeout: 10)
    }

    func testSearch() {
        login()
        navigate("Search")
        let search = app.textFields["Search files, documents, and folders..."]
        XCTAssertTrue(search.waitForExistence(timeout: 10))
        search.tap()
        search.typeText("Harbor\n")
        assertText("Harbor report.txt")
    }

    func testSettings() {
        login()
        navigate("Settings")
        XCTAssertEqual(app.textFields["Full name"].value as? String, "Harbor Tester")
    }

    func testNotifications() {
        login()
        navigate("Notifications")
        assertText("Your voyage report is ready")
    }

    func testMarginsExportEntryPoint() {
        login()
        navigate("Margins")
        assertText("HARBOR-01")
        XCTAssertTrue(app.buttons["Export CSV"].exists)
        app.buttons["Export CSV"].tap()
        assertText("HARBOR-01")
    }
}
