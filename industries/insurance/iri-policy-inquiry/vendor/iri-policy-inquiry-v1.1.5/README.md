
# Policy Inquiry API

## Overview

The **Policy Inquiry API** defines a standardized, read‑only interface for retrieving life and annuity policy information under the IRI **Digital‑First Architecture (DFA)** initiative. The API enables carriers, distributors, and solution providers to access consistent, authoritative policy data using modern RESTful patterns, replacing fragmented and tightly coupled legacy inquiry services.

This repository focuses exclusively on **policy inquiry and servicing use cases** and aligns with **OpenAPI 3.1.x** standards to ensure interoperability, scalability, and ease of integration across the industry.

---

## Business‑Focused Documentation

Business‑focused documentation, including use cases, scope definitions, and standards context, is maintained within the **https://github.com/Insured-Retirement-Institute/Digital-First-Specifications** materials associated with the Digital‑First initiative.

The site represents the published GitHub Pages output of the **Digital‑First‑Specifications** repository:

**https://specs.dfa.irionline.org/index.html**

---

## Business Context

### Problem Statement

- Policy inquiry data is distributed across legacy systems with inconsistent formats and interfaces.
- XML/SOAP‑based services increase integration complexity, operational risk, and onboarding effort.
- Downstream consumers require near real‑time, standardized access to policy servicing information.

### Objectives

- Provide a single, consistent API for policy inquiry across carriers and products.
- Modernize policy inquiry using REST/JSON and OAuth‑aligned security models.
- Improve data clarity, standardization, and integration efficiency.
- Support the broader Digital‑First strategy for scalable, interoperable data exchange.

---

## Key Features

- Inquiry‑focused RESTful API
- OpenAPI 3.1.x compliant specifications with reusable schema components
- Consistent request and response models across endpoints
- Standardized error handling and validation feedback
- Clear versioning and backward‑compatibility rules
- Alignment with industry data dictionary and DFA standards

---

## Capabilities & Scope

The Policy Inquiry API supports retrieval of comprehensive policy information, including but not limited to:

- **Policy Summary** – Policy identifiers, product details, status, carrier, and restrictions
- **Policy Values** – Account values, surrender values, loans, and withdrawal‑related values
- **Funds & Underlying Assets** – Fund‑level and segment‑level investment details
- **Parties** – Owners, annuitants, beneficiaries, payees, and contact information
- **Producers** – Writing and servicing producer details
- **Riders** – Rider elections, benefits, and lifecycle status
- **Dates** – Key policy lifecycle and administrative dates
- **Transactions** – Historical and recent policy transactions
- **Systematic Programs & Payouts** – Ongoing withdrawal, payout, and annuitization arrangements

All endpoints are **read‑only** and intended strictly for inquiry and servicing purposes. No create, update, or delete operations are supported.

---

## High‑Level Schema Concepts

The Policy Inquiry schema is organized around consistent, reusable concepts:

- **Policy Root** – Core identifiers, product attributes, policy status, and carrier metadata
- **Policy Values** – Monetary values, balances, and calculated servicing fields
- **Parties & Roles** – Policy‑related individuals and entities with defined role types
- **Producers** – Writing and servicing producer identifiers and affiliations
- **Riders & Benefits** – Optional coverages, elections, and rider‑specific attributes
- **Funds & Allocations** – Investment options, balances, and allocation details
- **Dates & Milestones** – Issue, effective, maturity, annuitization, and administrative dates

These concepts ensure consistent modeling and predictable consumption across platforms.

---

## Response Model Overview

### Success Responses

- Successful inquiries return **HTTP 200 OK**.
- Responses include structured policy data aligned with documented schemas.

---

## Standard Error Schema

All error responses follow a unified, predictable structure:

- HTTP status code (400–599)
- Structured error code (`domain.category.subcategory`)
- Technical diagnostic message
- User‑safe message suitable for display
- Correlation ID for end‑to‑end traceability
- Optional field‑level or business rule validation details

This approach ensures consistent diagnostics and cross‑system troubleshooting.

---

## OpenAPI Specifications

Interactive OpenAPI documentation and schema definitions are available at:

**https://specs.dfa.irionline.org/index.html**

---

## Versioning

- Current Version: **v1.1.5**
- Semantic versioning is applied
- Backward‑incompatible changes require a major version increment
- Draft and active versions are labeled per DFA governance

---

## Change Submissions and Reporting Issues

- Report bugs and enhancement requests via the repository **Issues** tab
- Change requests must follow Digital‑First standards governance workflows
- Security‑related issues must be reported through approved security channels

---

## Code of Conduct

All contributors and consumers must adhere to the repository **Code of Conduct** and applicable style guidelines to ensure consistent, professional collaboration.

---

## How to Contribute

- Fork the repository and submit pull requests for proposed changes
- Use the **Issues** tab for questions, defects, or enhancement proposals
- All contributions must align with Digital‑First standards review and approval processes

---

## Business Owners

- **Carrier Business Owner:** digitalfirst@irionline.org
- **Distributor Business Owner:** [contact]
- **Solution Provider Business Owner:** [contact]

---

