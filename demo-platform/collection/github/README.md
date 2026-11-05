# Reliability issue intake

Use the repository's Reliability request issue form to describe user impact, evidence and acceptance checks. The `devin` label marks an issue ready for the automation; the form does not apply the label automatically, so incomplete requests cannot launch work merely by opening an issue.

The later automation owner registers the GitHub trigger from the persona's organization UI. Choose the OtterWorks repository, the issue labeled event and exact label `devin`. Set creator execution when available, Fusion, an ACU cap of 10 and an invocation cap of 1 for the first proof. Point the automation at the reliability folder. Verify the session's owner, mode and issue link after the label fires.

Use `trigger.example.json` as a worksheet for the automation form. Copy the prompt and settings into the form, then confirm the UI's supported event filters. The prompt keeps changes on demo-bank and asks for a linked open PR. GitHub's `labeled` event supplies the issue URL, body and label; label removal and reapplication can fire another invocation, so check automation history before retrying.

The prerequisite creates the repository label and leaves issue creation to the later build. The later build proves a real issue-to-PR round trip and records Devin Review. Disable the automation after evidence capture when no further issues should start work.
