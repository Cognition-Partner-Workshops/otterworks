Feature: Inline file preview
  As a signed-in user
  I want to preview stored files inline
  So that I can inspect them without downloading

  @AC-01
  Scenario: Open a file preview from the list
    Given I have uploaded a preview text file
    When I choose Preview from the Files list
    Then the inline preview shows its text without downloading

  @AC-04 @AC-11 @AC-12
  Scenario: Render image and media files inline
    Given I have uploaded a preview image
    When I open its detail route
    Then the image is shown inline
    Given I have uploaded a preview audio file
    When I open its detail route
    Then native audio controls are shown
    Given I have uploaded a preview video file
    When I open its detail route
    Then native video controls are shown

  @AC-06 @AC-10
  Scenario: Render PDF and tabular text files
    Given I have uploaded a preview PDF file
    When I open its detail route
    Then the PDF frame and safe new-tab link are shown
    Given I have uploaded a preview CSV file
    When I open its detail route
    Then the first CSV row is shown as headers

  @AC-04 @AC-05 @AC-06 @AC-07 @AC-09 @AC-10 @AC-11 @AC-12
  Scenario: Render common previewable file types
    Given I have uploaded a preview Markdown file
    When I open its detail route
    Then the Markdown heading and Rendered toggle are shown

  @AC-13 @AC-14 @AC-15 @AC-16 @AC-17 @AC-18
  Scenario: Render archives and office documents with a fallback for unknown bytes
    Given I have uploaded a preview ZIP file
    When I open its detail route
    Then the archive entry is listed without extraction
    Given I have uploaded a preview unknown binary
    When I open its detail route
    Then the unsupported type message and Download button are shown

  @AC-08 @AC-28 @AC-29 @AC-30
  Scenario: Handle bounded content and preview failures
    Given I have uploaded a preview text file
    When I open its detail route
    Then its content is loaded with a byte range

  @AC-28
  Scenario: Refresh a storage URL after its first request fails
    Given I have uploaded a preview image whose first storage request fails
    When I open its detail route
    Then the image is shown inline after a URL refresh

  @AC-29
  Scenario: Show recovery actions for a corrupt DOCX
    Given I have uploaded a corrupt preview DOCX file
    When I open its detail route
    Then the preview error and recovery actions are shown
