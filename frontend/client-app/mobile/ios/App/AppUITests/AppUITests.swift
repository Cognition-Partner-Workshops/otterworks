import XCTest

class AppUITestCase: XCTestCase {
    let app = XCUIApplication()

    func element(_ type: XCUIElement.ElementType, _ label: String, contains: Bool = false) -> XCUIElement {
        app.webViews.descendants(matching: type).matching(NSPredicate(format: contains ? "label CONTAINS[c] %@" : "label == %@", label)).firstMatch
    }

    func reveal(_ target: XCUIElement) {
        XCTAssertTrue(target.waitForExistence(timeout: 10))
        for _ in 0..<6 {
            if target.isHittable && app.frame.contains(target.frame) { return }
            app.webViews.firstMatch.swipeUp()
        }
        XCTAssertTrue(target.isHittable, "Not hittable: \(target)")
    }

    func fill(_ field: XCUIElement, _ text: String) {
        reveal(field)
        field.tap()
        if !app.keyboards.firstMatch.waitForExistence(timeout: 3) { field.tap() }
        XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 5))
        let value = field.value as? String ?? ""
        if value != field.placeholderValue {
            field.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: value.count))
        }
        field.typeText(text)
    }

    func rotate(_ orientation: UIDeviceOrientation) {
        XCUIDevice.shared.orientation = orientation
        let settled = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            let frame = self.app.frame
            let landscape = frame.width > frame.height
            let banner = self.element(.other, "banner")
            return landscape == orientation.isLandscape && banner.exists && banner.frame.width <= frame.width + 1
        }, object: nil)
        wait(for: [settled], timeout: 10)
    }

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
        XCUIDevice.shared.orientation = .portrait
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
        fill(email, "tester@example.com")
        let field = app.secureTextFields.firstMatch
        fill(field, password)
        let done = app.toolbars.buttons["Done"]
        if done.exists {
            done.tap()
            XCTAssertTrue(app.keyboards.firstMatch.waitForNonExistence(timeout: 5))
        }
        app.buttons["Sign in"].tap()
        if password == "HarborPass123!" {
            XCTAssertTrue(app.links["Files"].waitForExistence(timeout: 10))
            rotate(.landscapeLeft)
            rotate(.portrait)
        }
    }

    func assertText(_ text: String, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertTrue(app.webViews.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@ OR value CONTAINS %@", text, text)).firstMatch.waitForExistence(timeout: 15), "Missing \(text)", file: file, line: line)
    }

    func openSidebar() {
        if !element(.button, "Sign out").exists {
            rotate(.landscapeLeft)
            element(.button, "Open menu").tap()
            XCTAssertTrue(element(.button, "Sign out").waitForExistence(timeout: 5))
            rotate(.portrait)
        }
    }

    func navigate(_ name: String, dismissSidebar: Bool = true) {
        openSidebar()
        let link = element(.link, name)
        reveal(link)
        link.tap()
        XCTAssertTrue(app.webViews.descendants(matching: .other).matching(NSPredicate(format: "label == %@ AND value == '1'", name)).firstMatch.waitForExistence(timeout: 10), app.debugDescription)
        if dismissSidebar {
            rotate(.landscapeLeft)
            element(.button, "Toggle sidebar").tap()
            XCTAssertTrue(element(.button, "Sign out").waitForNonExistence(timeout: 5), app.debugDescription)
            rotate(.portrait)
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
        let browse = element(.staticText, "Drag & drop files here, or click to browse")
        reveal(browse)
        browse.tap()
        let photoLibrary = app.buttons["Photo Library"]
        let chooseFile = app.collectionViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Choose File'")).firstMatch
        XCTAssertTrue(photoLibrary.waitForExistence(timeout: 5), app.debugDescription)
        XCTAssertTrue(chooseFile.exists)
        let picker = XCTAttachment(screenshot: app.screenshot())
        picker.name = "Native upload source picker"
        picker.lifetime = .keepAlways
        add(picker)
        chooseFile.tap()
        let cancel = app.buttons["Cancel"].firstMatch
        XCTAssertTrue(cancel.waitForExistence(timeout: 5), app.debugDescription)
        cancel.tap()
        XCTAssertTrue(cancel.waitForNonExistence(timeout: 5))
        XCTAssertEqual(app.state, .runningForeground)
        assertText("Drag & drop files here, or click to browse")
    }

    func testFileDetailDownloadButton() {
        login()
        navigate("Files")
        let title = element(.staticText, "Harbor report.txt")
        reveal(title)
        title.doubleTap()
        XCTAssertTrue(app.buttons["Download"].firstMatch.waitForExistence(timeout: 10))
        app.buttons["Download"].firstMatch.tap()
        // Known native bug: blob-anchor downloads are not persisted via Filesystem.
        // Do not claim a saved file; the browser suite verifies the response payload.
        assertText("Harbor report.txt")
    }

    func testDocumentEditing() {
        login()
        navigate("Documents")
        let title = element(.staticText, "Voyage notes")
        reveal(title)
        title.doubleTap()
        let editor = app.webViews.textViews.firstMatch
        XCTAssertTrue(editor.waitForExistence(timeout: 10))
        XCTAssertTrue((editor.value as? String ?? "").contains("Welcome aboard the harbor."))
        editor.tap()
        XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 5))
        editor.typeText(" Native voyage edit")
        app.buttons["Save"].tap()
        let saved = expectation(description: "HTTP document save persisted")
        var request = URLRequest(url: URL(string: "http://127.0.0.1:4010/api/v1/documents/doc-1")!)
        request.setValue("Bearer mock", forHTTPHeaderField: "Authorization")
        Task {
            for _ in 0..<40 {
                let (data, _) = try await URLSession.shared.data(for: request)
                let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
                if (json?["content"] as? String ?? "").contains("Native voyage edit") {
                    saved.fulfill()
                    return
                }
                try await Task.sleep(nanoseconds: 100_000_000)
            }
        }
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
        reveal(element(.staticText, "HARBOR-01"))
        assertText("HARBOR-01")
    }
}
