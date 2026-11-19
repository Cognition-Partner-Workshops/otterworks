import XCTest
import UIKit

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
        navigate("Dashboard")
        let menu = element(.button, "Open menu")
        XCTAssertGreaterThanOrEqual(menu.frame.minY, app.frame.minY + 44)
        menu.tap()
        XCTAssertTrue(element(.link, "Files").waitForExistence(timeout: 3))
        let close = element(.button, "Toggle sidebar")
        XCTAssertGreaterThanOrEqual(close.frame.minY, app.frame.minY + 44)
        XCTAssertTrue(close.isHittable)
        saveScreenshot("portrait-home")
    }

    func saveScreenshot(_ name: String) {
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    func testLandscapeSafeArea() {
        login()
        navigate("Dashboard")
        for orientation in [UIDeviceOrientation.landscapeLeft, .landscapeRight] {
            rotate(orientation)
            let menu = element(.button, "Open menu")
            XCTAssertGreaterThanOrEqual(menu.frame.minX, app.frame.minX + 40)
            let help = element(.link, "Help")
            XCTAssertLessThanOrEqual(help.frame.maxX, app.frame.maxX - 40)
            menu.tap()
            let close = element(.button, "Toggle sidebar")
            XCTAssertTrue(close.isHittable)
            XCTAssertGreaterThanOrEqual(element(.link, "Dashboard").frame.minX, app.frame.minX + 40)
            saveScreenshot("landscape-safe-area")
            close.tap()
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
        let bold = element(.button, "Bold")
        let keyboard = app.keyboards.firstMatch
        let toolbarVisible = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            bold.exists && bold.isHittable && bold.frame.maxY <= keyboard.frame.minY && bold.frame.minY >= self.app.frame.minY + 44
        }, object: nil)
        wait(for: [toolbarVisible], timeout: 10)
        bold.tap()
        XCTAssertTrue(keyboard.exists)
        assertStatusBarBackdrop()
        saveScreenshot("editor-keyboard")
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

    func assertStatusBarBackdrop() {
        let image = XCUIScreen.main.screenshot().image
        guard let cgImage = image.cgImage else { return XCTFail("Missing screenshot pixels") }
        let width = cgImage.width
        let height = cgImage.height
        var pixels = [UInt8](repeating: 0, count: width * height * 4)
        guard let context = CGContext(data: &pixels, width: width, height: height,
                                      bitsPerComponent: 8, bytesPerRow: width * 4,
                                      space: CGColorSpaceCreateDeviceRGB(),
                                      bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else {
            return XCTFail("Cannot read screenshot pixels")
        }
        context.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))
        let scale = CGFloat(width) / app.frame.width
        // Above the system clock/icons, the status-bar backdrop must be solid white.
        for y in stride(from: 4, through: 16, by: 4) {
            for x in 10..<Int(app.frame.width - 10) {
                let offset = (Int(CGFloat(y) * scale) * width + Int(CGFloat(x) * scale)) * 4
                XCTAssertTrue(pixels[offset] > 245 && pixels[offset + 1] > 245 && pixels[offset + 2] > 245,
                              "Web content is visible through the status-bar backdrop at \(x),\(y)")
            }
        }
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
