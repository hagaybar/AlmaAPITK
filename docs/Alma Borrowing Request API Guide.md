# **Engineering Guide for Alma ILS Borrowing Request API Integration**

> **Revision note (2026-05-18):** This guide was originally compiled from
> multiple sources. A schema audit against the authoritative Alma XSD
> (`rest_user_resource_sharing_request.xsd`, retrieved from the Ex Libris
> developer network) surfaced several inaccuracies in the field-schema
> table and the payload examples that would cause requests to be rejected
> by Alma's JAXB deserializer if followed verbatim. The corrected schema,
> codes, mandatory-field set, and JSON wrapping conventions are reflected
> in this revision; what was wrong is footnoted where helpful so future
> readers don't re-step on the same rakes. The Validation Checkpoints
> table and the Configuration Dependencies sections (which were the most
> valuable parts of the original) are preserved largely unchanged.

## **Architectural Paradigm of Resource Sharing Workflows**

Implementing a programmatic interface for borrowing requests within the Ex Libris Alma Integrated Library System (ILS) requires a comprehensive understanding of the resource-sharing lifecycle. Resource sharing borrowing requests represent specialized inter-library loan operations executed within Alma to obtain physical or digital assets from external consortial or peer partners.1 When transitioning these operations from staff-mediated user interfaces to automated API-driven layers, developers must account for multiple creation paths, bibliographic matching pipelines, and discovery integrations.

### **Discovery Integration and Bibliographic Matching**

Resource sharing is closely integrated with the discovery layer, typically Primo VE.3 Under standard configurations, patrons initiate borrowing requests during discovery when search queries reveal that a required resource is unavailable within the institution's local physical or electronic holdings.1 The system calculates real-time requestability and loan availability, displaying options for resource-sharing requests directly to authenticated users.5

To improve the match rates of incoming requests against external collections, Primo VE utilizes the Alma Link Resolver to handle OpenURL queries.3 For electronic materials, this resolver evaluates records within the Central Discovery Index (CDI).3 An enhancement allows Primo VE to pass up to five ISBNs and EISBNs within an OpenURL request using the parameters rft.isbn\_list and rft.eisbn\_list.3 The Link Resolver stores these identifiers within the context object (CTO) to match against active portfolios, ensuring that requests are routed using exact matches and reducing errors in downstream borrowing pipelines.3

To facilitate manual or automated inputs from external search indices such as Google Scholar, the system supports metadata entry from external sources directly into the resource-sharing form.6 Integrators can also leverage cloud applications to cross-reference search databases such as Trove.7 These applications retrieve records using metadata harvested from local bibliographic records and active resource-sharing requests to determine other holding libraries before routing requests.7

### **Staff-Mediated and Automated Pipelines**

For requests managed or initiated by library staff, Alma provides several workflows designed to minimize manual data entry and expedite fulfillment.1 Staff can execute searches within the local repository or target external catalogs using integration profiles to automatically generate pre-populated requests.1

When completing a request, the workflow terminates with one of several key system actions.1 Selecting *Locate* saves the transaction and triggers the automated locate process to identify potential lenders along a configured partner rota.1 Selecting *Send* bypasses automated profiling to immediately transmit a request message to a designated active partner, provided the "Automatically activate locate profile" parameter is disabled.1 Operators may also choose to *Save* the request as a draft or *Save and Edit* to open multi-tab menus for detailed structural modifications.1

Recent user interface upgrades support dual-pane navigation, allowing staff to edit request details, assign records, and resolve queries without losing their list context.9 Status changes such as "Will Supply" can be transmitted from lenders to halt automatic expiration cycles.10 Patrons can track active and historical requests (including cancelled transactions) directly within their library accounts, and submit online inquiries that route directly to staff task lists.4

## ---

**API Technical Specification and Field Schemas**

Programmatically executing a borrowing request is accomplished via the Alma REST API framework.2 Specifically, integrations target the resource-sharing requests endpoint, binding the transaction to a unique patron record.2

HTTP

POST /almaws/v1/users/{user\_id}/resource-sharing-requests

To invoke this endpoint, client applications authenticate using a standard Alma REST API key passed as `Authorization: apikey <key>`. The `user_id` is supplied as a path parameter on the URL. The institution code and operational scope are derived from the API key's configured permissions. (The original guide incorrectly described a JWT-based auth mechanism; the Alma REST surface used by this and analogous endpoints uses API-key auth.)

### **REST API Schema Fields**

> **JSON encoding convention.** The XSD declares most code-table fields
> as simple string types, but Alma's JSON representation **wraps**
> code-table values in an object with a `value` key (and an optional
> `desc` on the response side). Treat the "JSON shape" column below as
> authoritative for what to send. The single notable exception is
> `owner`, which is a **plain string** in JSON despite being a library
> code — a long-documented Alma quirk that also applies to lending
> requests.

| Field Name | Data Type | JSON shape | Requirement | System Description and Functional Mapping |
| :---- | :---- | :---- | :---- | :---- |
| `title` | String | plain | Required (unless `mms_id` supplied) | The title of the requested resource. Acts as the primary search index for external catalog queries and locating profiles. |
| `citation_type` | Code-table | `{"value": "<code>"}` | Required | Type of the requested resource. **For BORROWING requests** the codes are `BK` (book) and `CR` (continuing resource / serial). NOTE: lending requests use the codes `BOOK` / `JOURNAL`; purchase requests use `BOOK` / `JOURNAL`. The original guide's "BOOK or ARTICLE" was wrong for the borrowing surface. |
| `format` | Code-table | `{"value": "<code>"}` | Required | Format of the resource requested. Valid codes for borrowing are `PHYSICAL` and `DIGITAL`. NOTE: the original guide called this field `requested_format` — that name does not exist in the XSD and Alma will silently ignore it; the real field name is `format`. |
| `pickup_location_type` | String | plain | Optional but recommended | Pickup location type. Documented values: `LIBRARY`, `CIRCULATION_DESK`. Plain string in JSON (not wrapped). |
| `pickup_location` | Code-table | `{"value": "<library_code>"}` | Required (for physical borrowing) | The pickup library code where the resource will be delivered. JSON-wrapped despite being a string in the XSD. Personal-delivery (home / work address) is handled separately via `use_alternative_address` + `text_email` / `text_postal_*`, not via this field. |
| `agree_to_copyright_terms` | Boolean | plain | **Mandatory for borrowing** | Indication whether the requester has agreed to the copyright terms. The original guide omitted this field — a payload following the original guide verbatim would be rejected by Alma for missing this mandatory borrowing-side flag. |
| `owner` | String | **plain** (not wrapped — see note above) | Required | The unique code of the Resource Sharing Library managed by the institution that holds operational ownership of the request. Same plain-string quirk as `ResourceSharing.create_lending_request`. |
| `requester` | Object | (output-only) | Do not send | Derived by Alma from the `user_id` in the URL path. The XSD lists `requester` on the schema, but at POST time it is output-only — sending it has no documented effect. |
| `author` | String | plain | Optional | Primary creator. Used by locate engines to filter matching bibliographic search results. |
| `isbn` | String | plain | Optional | International Standard Book Number. Evaluated by backend matching rules to pair orders with existing portfolios. |
| `issn` | String | plain | Optional | International Standard Serial Number. Utilized for matching serials and journals during electronic resource processing. |
| `doi` | String | plain | Optional | Digital Object Identifier. If supplied alongside an active Augmentation-Integration Profile, triggers background lookups. |
| `pmid` | String | plain | Optional | PubMed Identifier. Used in tandem with DOI to auto-populate bibliographic metadata, overwriting manual values. |
| `partner` | Code-table | `{"value": "<code>"}` | **Optional for borrowing**, mandatory for lending | Specific partner library code. Used to bypass automated rota matching and route the transaction directly. NOTE: this contradicts older folklore that "borrowing requests require a partner at create time"; the XSD plus empirical SANDBOX testing both confirm partner is *not* required at borrowing-create — partner gets attached later, during the Locate / Send Request workflow steps. |
| `mms_id` | String | plain | Optional | MMS ID of the requested resource. Relevant primarily after physical material is received and cataloged, or if the requester searched the local catalog first. At create time for a typical borrowing scenario, the item is not in the local catalog (that's why it's being borrowed) — `title` is the more common identifier. |
| `allow_other_formats` | Boolean | plain | Optional | Indication whether other formats besides `format` are acceptable. (Note: plural — the original guide used the singular `allow_other_format` which is not in the XSD.) |
| `last_interest_date` | Date string | plain | Optional | ISO-formatted date — last date the request is needed. |
| `level_of_service` | Code-table | `{"value": "<code>"}` | Optional | Service level code from `LevelOfService` code table. JSON-wrapped. |
| `note` | String | plain | Optional | General note. |

### **Automatic Bibliographic Augmentation**

A primary advantage of integrating via the REST API is the ability to leverage Alma’s background Augmentation-Integration Profiles.1 If an integration layer sends an API payload containing a valid persistent identifier, such as a doi or pmid, the system automatically resolves the citation parameters.1

Alma queries global databases to retrieve metadata such as chapter titles, volume designations, issue numbers, precise page ranges, and publication dates, writing these values directly into the resource-sharing record.1 This automated process overwrites any corresponding manually provided metadata strings in the payload, ensuring data accuracy for downstream lenders.1

## ---

**Patron-Level Validation Pipelines and Execution Blocks**

Before Alma accepts and registers a borrowing request, the transactional engine runs a validation pipeline.12 This pipeline evaluates the patron's status, institutional rules, and local holdings.12 If any check fails, Alma blocks the request, displaying specific error codes in the API response or hiding request options in the discovery interface.8

### **Validation Checkpoints**

| Checkpoint Name | Target Data Model Attribute | Evaluation Condition | Failure Resolution |
| :---- | :---- | :---- | :---- |
| **Account Blocks** | User Record Blocks Tab | Evaluates whether any active block applied to the user account explicitly includes the "ILL" action type.12 | Resolve blocks or clear outstanding fees exceeding thresholds in the user profile.12 |
| **Role Validity** | User Roles | Verifies the presence of an active, non-expired "Patron" role scoped to the Resource Sharing Library or the overall Institution.12 | Provision or extend the patron role within the appropriate library or institutional scope.12 |
| **Requester Expiration** | isExpiredRequester | Compares the user account expiration date against the current system transaction date.12 | Update user record expiration limits to restore account activity.12 |
| **Format Authorization** | Borrowing RS TOU | Evaluates whether the "Allow Requesting" policy is set to TRUE for the requested format (PHYSICAL, DIGITAL, etc.).12 | Adjust rule hierarchy in the Fulfillment Unit to permit the requested format for the user's group.12 |
| **Velocity Limits** | TOU Limits | Evaluates active and annual request counts against the "Active Resource Sharing Requests Limit" and "Yearly Requests Limit" policies.12 | Wait for existing requests to complete, or override limit policies within the relevant Terms of Use (TOU).12 |
| **Library Status** | RS Library Setup | Checks if the "Temporarily Inactive for Borrowing" parameter is active for the target Resource Sharing Library.8 | Deactivate the temporary inactivity status or adjust active date ranges in library details.8 |
| **Local Availability** | Link Resolver (UResolver) | Checks if a matching, requestable resource is already held in the local physical or electronic collection.1 | System issues a warning; API calls can override this if parameterized to force external processing.1 |

### **Electronic Resource Rejection Logic**

For electronic resource sharing, institutions must configure rules to manage licensing restrictions and prevent violations.8 When a borrowing locate profile executes, Alma can evaluate the licensing terms of matching electronic assets.8

Under the Resource Sharing Library setup, administrators configure Electronic Rejection Rules.8 These rules automatically block or reject incoming requests if the matching electronic resource is linked to restrictive license terms.8 These terms include "Interlibrary Loan Electronic", "Interlibrary Loan Print Or Fax", "Interlibrary Loan Record Keeping Required Indicator", and "Interlibrary Loan Secure Electronic Transmission".8

Furthermore, if the "Ignore electronic resources" parameter is checked, locate profiles will bypass electronic matches entirely, routing physical fulfillment requests.8

## ---

**Configuration Dependencies and Policy Mapping**

Programmatically submitting borrowing requests requires corresponding backend configurations within the Alma fulfillment and library structures.15 Without these definitions, requests submitted via the API will trigger policy errors.12

### **Resource Sharing Library and Location Modeling**

Every borrowing request must be owned by an organizational unit configured as a Resource Sharing Library.1 To support inventory tracking, the library must not be marked as "Itemless".15

Physical items processed for resource sharing must route through a dedicated Resource Sharing Location.15 This location must be linked to the library's primary circulation desk.15 This setup ensures that when items are checked out for resource sharing, the system updates their location status to reflect that they are in use for external fulfillment.15

Alma Configuration \-\>  
    Fulfillment \-\> Locations \-\> Physical Locations \-\> Add Location (e.g., Code: RShare)  
    Attach Desk \-\> Select Primary Circulation Desk

### **Fulfillment Unit Rules and TOU Structures**

Fulfillment policies are governed by rules within designated Fulfillment Units.15 Within the Resource Sharing Fulfillment Unit, administrators must establish rule hierarchies for both loan and borrowing behaviors.15

| Rule Type | Rule Name | Parameters / Conditions | Applied Terms of Use (TOU) |
| :---- | :---- | :---- | :---- |
| **Borrowing Resource Sharing** | Borrowing Resource | User Group In List 15 | **Borrowing Resource Sharing TOU**: Defines format permissions and velocity limits.12 |
| **Lending Resource Sharing** | Lending Resource | Partner In List \[List of Peer P2P Partners\]16 | **Lending Resource Sharing TOU**: Establishes lending rules for external consortial partners.15 |
| **Loan** | Resource Sharing Loan | Location \= Resource Sharing Location 15 | **RShare Loan TOU**: Dictates loan periods and renewal behaviors for temporary items.15 |

### **Workflow Profiles and Temporary Item Creation**

To automate request lifecycles, institutions use Workflow Profiles to map specific status transitions.16 For peer-to-peer (P2P) borrowing, profiles must support various transactional states, including automatic renewals, partner-initiated cancellations, staff cancellations, and status updates such as "Will Supply".10

Additionally, Temporary Item Creation Rules are required to process physical items received from external partners.16 These rules automatically generate a temporary local record, assign a temporary barcode, and apply standard circulation rules based on the partner's profile.16

## ---

**Programmatic API Execution and Payload Blueprints**

The following templates represent the JSON payload structures sent via the REST client to initiate borrowing requests.

### **Minimalist Request Payload (Utilizing Automated Augmentation)**

This payload relies on backend augmentation profiles. By providing a `doi` or `pmid`, the client submits minimal metadata, allowing Alma to resolve bibliographic details during the automated locate process.

```json
{
  "title": "Placeholder Title for Augmentation",
  "citation_type": {"value": "CR"},
  "format": {"value": "DIGITAL"},
  "owner": "<RS_LIBRARY_CODE>",
  "pickup_location_type": "LIBRARY",
  "pickup_location": {"value": "<PICKUP_LIBRARY_CODE>"},
  "agree_to_copyright_terms": true,
  "doi": "10.1016/j.chb.2020.106305",
  "note": "Automated API request. Resolving metadata via DOI."
}
```

Key corrections vs. the original guide: `citation_type` is wrapped and uses the borrowing-side code `CR` (continuing resource — appropriate for a journal article via DOI); `requested_format` is renamed to `format` and wrapped; `pickup_location` is wrapped and accompanied by `pickup_location_type`; and `agree_to_copyright_terms: true` is added because the XSD marks it mandatory for borrowing.

### **Explicit Bibliographic Payload (Forcing Manual Metadata)**

This schema is used when bypassing background lookups or when the requesting source is an external proprietary catalog.

```json
{
  "title": "Introduction to Algorithms",
  "author": "Cormen, Thomas H.",
  "citation_type": {"value": "BK"},
  "format": {"value": "PHYSICAL"},
  "owner": "<RS_LIBRARY_CODE>",
  "pickup_location_type": "LIBRARY",
  "pickup_location": {"value": "<PICKUP_LIBRARY_CODE>"},
  "agree_to_copyright_terms": true,
  "isbn": "9780262033848",
  "publisher": "MIT Press",
  "year": "2009",
  "edition": "3rd ed.",
  "volume": "1",
  "allow_other_formats": true,
  "level_of_service": {"value": "REGULAR"},
  "note": "Fulfill via physical partner rota only."
}
```

Key corrections vs. the original guide: `citation_type` is wrapped and uses the borrowing-side code `BK` (book — NOT `BOOK`, which is the lending-side code); `requested_format` is renamed to `format` and wrapped; `publication_date` becomes `year` per the XSD; `allow_other_format` becomes `allow_other_formats` (plural, per the XSD); `level_of_service` is wrapped; `pickup_location` is wrapped and accompanied by `pickup_location_type`; `agree_to_copyright_terms: true` added.

## ---

**Interoperability and NCIP Protocol Workflows**

For institutions using external inter-library loan engines such as OCLC ILLiad or Tipasa, Alma coordinates transactional states using the NISO Circulation Interchange Protocol (NCIP).13

### **The NCIP Transaction Lifecycle**

When an external system receives and processes an item, it initiates an NCIP exchange with Alma.13

1. **AcceptItem Phase**: The external system sends an AcceptItem message to Alma's NCIP servlet, passing parameters such as the patron's identifier, a brief bibliographic record, the unique item barcode, and the lender's due date.13 Alma validates the user identifier and creates a temporary item record in the designated "Borrowing Resource Sharing Requests" location.13 The system then places an active hold on this temporary item for the patron.17  
2. **CheckoutItem Phase**: When the patron picks up the physical item, a CheckoutItem event is triggered.13 Alma uses the due date supplied by the external system, overriding standard local circulation rules.13  
3. **Return and Delete Phase**: When the item is returned, the check-in event in the external system sends a message to Alma.13 This updates the item status and removes the temporary record from the patron's account, completing the transaction.13

### **Managing NCIP Routing Failures**

Developers and administrators must monitor failure queues within the integration layer to prevent transaction gaps.17

| NCIP Routing Queue | System Failure Condition | Remediation Action |
| :---- | :---- | :---- |
| BorrowingAcceptItemFailQueue | Alma cannot create a brief bibliographic record or apply a patron hold due to format validation or account block issues.12 | Check user blocks, verify active roles, or review the mapping of user identifiers between systems.12 |
| BorrowingCheckInItemFailQueue | Triggered when a loan is marked returned in the external system, but Alma fails to clear the checkout or delete the temporary record.13 | Verify return protocols, check the status of the item, or manually clear outstanding checkouts in the patron's account.13 |
| LendingCheckOutItemFailQueue | Occurs when an item is marked as found by lending staff, but the system fails to transition the asset to the Resource Sharing Library.13 | Review physical location mapping table parameters and verify active desk associations in the lending configuration.13 |

## ---

**Financial Integrations and Administrative Lifecycles**

Resource-sharing operations often carry financial implications that must be managed alongside the request lifecycle.11 These include service fees, transactional billing, and fund tracking.11

### **Fund Encumbrances and Rollover**

When resource-sharing requests incur costs from external suppliers, institutions can link these expenses to specific internal funds.11 When a request is created, the estimated cost can be encumbered against the designated fund.11

Active Resource Sharing Request \-\> Associated with Fund Code (e.g., ILL\_FUND)  
    System Encumbers Cost \-\> Subtracts from active fiscal period balance

During fiscal year-end processes, Alma runs a resource-sharing request rollover job.11 This job identifies active requests that still carry encumbrances and copies them to the new fiscal period.11 This preserves financial tracking across fiscal periods without requiring manual reconciliation by library staff.11

For user-facing fees, Alma integrates with external payment gateways.11 When a request is completed, calculated fees are recorded on the patron's account and can be settled online using payment integration profiles.11

### **Administrative Job Lifecycles**

Alma manages resource-sharing statuses through background system jobs.14

* **Expired Resource Sharing Requests**: Runs daily at 02:00 to identify and cancel pending requests that have exceeded their active validation periods.16  
* **Claim Resource Sharing Request**: Automatically cancels borrowing requests sent to lenders that have not been shipped or acknowledged within a configurable number of days.19  
* **Send Overdue Message to Resource Sharing Borrower Partner**: Monitored by lenders to manage overdue notices sent to consortial partners.19  
* **Send Courtesy Notices and Handle Loan Renewals**: Aggregates loan notifications and coordinates renewal requests with external partners.14

## ---

**Architectural Best Practices and Risk Management**

To build a reliable API integration for borrowing requests, developers must implement error handling and safeguard against common system issues.

### **Handling Temporary Service Outages**

When an institution temporarily suspends borrowing operations, administrators check the "Temporarily Inactive for Borrowing" setting in the Resource Sharing Library configuration.8 This setting blocks request creation across the UI, Primo discovery, and the REST API.8

Integrating applications should proactively handle the error payloads generated during these inactive periods. Rather than displaying generic system failures, the middleware should detect the specific block condition and inform the user of the temporary service suspension.8

### **Managing Search and Discovery Fallbacks**

Integrations should leverage automated fail-safes to manage requests that cannot be routed.8 If "Cancel request on locate failure" is active, requests that fail the automated locate process are immediately cancelled by the system.8

To prevent valid patron requests from being lost, developers can use "Sending Borrowing Request Rules" to enforce staff mediation.19 By setting the default routing rule output to FALSE, any request that fails the automated locate check is preserved in the Borrowing Requests task list with a status of Ready to be Sent.19 This allows staff to review the request, adjust bibliographic details, or manually assign alternative partner rotas to fulfill the transaction.1

#### **Works cited**

1. Creating a Borrowing Request \- Ex Libris Knowledge Center, accessed on May 18, 2026, [https://knowledge.exlibrisgroup.com/Alma/Product\_Documentation/010Alma\_Online\_Help\_(English)/030Fulfillment/050Resource\_Sharing/010Resource\_Sharing\_Workflow/Borrowing\_Requests/010Creating\_a\_Borrowing\_Request](https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/010Alma_Online_Help_\(English\)/030Fulfillment/050Resource_Sharing/010Resource_Sharing_Workflow/Borrowing_Requests/010Creating_a_Borrowing_Request)  
2. SUNYLA Midwinter 2025 \- Alma Borrowing Request Sender, accessed on May 18, 2026, [https://sunyla.org/sunyla\_docs/conferences/presentations/midwinter25/Session5\_SUNYLA%20Midwinter%202025%20-%20Alma%20Borrowing%20Request%20Sender.pdf](https://sunyla.org/sunyla_docs/conferences/presentations/midwinter25/Session5_SUNYLA%20Midwinter%202025%20-%20Alma%20Borrowing%20Request%20Sender.pdf)  
3. ERM & CDI \- ULMS Guide, accessed on May 18, 2026, [https://ulmsguide.calstate.edu/book/export/html/28](https://ulmsguide.calstate.edu/book/export/html/28)  
4. 2023 Primo Enhancements \- ODIN, accessed on May 18, 2026, [https://www.odin.nodak.edu/sites/default/files/2023-03/2023%20Primo%20Enhancements%20-%20Round%201.xlsx](https://www.odin.nodak.edu/sites/default/files/2023-03/2023%20Primo%20Enhancements%20-%20Round%201.xlsx)  
5. Primo VE 2019 Release Notes \- Ex Libris Knowledge Center, accessed on May 18, 2026, [https://knowledge.exlibrisgroup.com/Primo/Release\_Notes/002Primo\_VE/0972019/002Primo\_VE\_2019\_Release\_Notes](https://knowledge.exlibrisgroup.com/Primo/Release_Notes/002Primo_VE/0972019/002Primo_VE_2019_Release_Notes)  
6. Primo 2022 \- ODIN, accessed on May 18, 2026, [https://www.odin.nodak.edu/sites/default/files/2022-03/Primo%20enhancements%20-%20round%201%20voting%2020220321.xlsx](https://www.odin.nodak.edu/sites/default/files/2022-03/Primo%20enhancements%20-%20round%201%20voting%2020220321.xlsx)  
7. nishen/eca-trove-search: Ex Libris Cloud App for searching Trove. \- GitHub, accessed on May 18, 2026, [https://github.com/nishen/eca-trove-search](https://github.com/nishen/eca-trove-search)  
8. Configuring Parameters of a Resource Sharing Library \- Ex Libris Knowledge Center, accessed on May 18, 2026, [https://knowledge.exlibrisgroup.com/Alma/Product\_Documentation/010Alma\_Online\_Help\_(English)/030Fulfillment/050Resource\_Sharing/Resource\_Sharing\_Configuration/030Configuring\_Parameters\_of\_a\_Resource\_Sharing\_Library](https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/010Alma_Online_Help_\(English\)/030Fulfillment/050Resource_Sharing/Resource_Sharing_Configuration/030Configuring_Parameters_of_a_Resource_Sharing_Library)  
9. Alma 2022 Release Notes \- Ex Libris Knowledge Center, accessed on May 18, 2026, [https://knowledge.exlibrisgroup.com/Alma/Release\_Notes/2022/Alma\_2022\_Release\_Notes](https://knowledge.exlibrisgroup.com/Alma/Release_Notes/2022/Alma_2022_Release_Notes)  
10. Alma September 2015 Release Notes \- ODIN, accessed on May 18, 2026, [https://www.odin.nodak.edu/sites/default/files/alma\_september\_2015\_release\_notes.pdf](https://www.odin.nodak.edu/sites/default/files/alma_september_2015_release_notes.pdf)  
11. STATE OF NORTH CAROLINA, accessed on May 18, 2026, [https://wordpress.nccommunitycolleges.edu/wp-content/uploads/2026/03/Ex-Libris-ILS-50-2425002-Executed-Response.pdf](https://wordpress.nccommunitycolleges.edu/wp-content/uploads/2026/03/Ex-Libris-ILS-50-2425002-Executed-Response.pdf)  
12. What can be the reasons why a patron doesn't have access to the ..., accessed on May 18, 2026, [https://knowledge.exlibrisgroup.com/Alma/Knowledge\_Articles/What\_can\_be\_the\_reasons\_why\_a\_patron\_doesn't\_have\_access\_to\_the\_Blank\_Resource\_Sharing\_Request\_form\_in\_the\_Discovery%3F](https://knowledge.exlibrisgroup.com/Alma/Knowledge_Articles/What_can_be_the_reasons_why_a_patron_doesn't_have_access_to_the_Blank_Resource_Sharing_Request_form_in_the_Discovery%3F)  
13. vculibraries/alma-ncip: Plugin to integrate Ex Libris Alma and ILLiad client using NCIP, accessed on May 18, 2026, [https://github.com/vculibraries/alma-ncip](https://github.com/vculibraries/alma-ncip)  
14. Alma January 2020 Release Notes, accessed on May 18, 2026, [https://files.mtstatic.com/site\_11811/78022/0?Expires=1777355777\&Signature=KPfZvm6amQKnUx7tulJ4spbW4AmFbNQB366RYK86OlztC8BPQG-SihzkARVvhGFqXkqvZqmhsyClWPx15K9kC5FucxRfuOr6cJCTEyYLdaSjohXh9\~lnChTleDhKj9efOLp2aO9hFz-WGNbOAkylsRaM2yQSDb4YZzN3UNjnYoA\_\&Key-Pair-Id=APKAJ5Y6AV4GI7A555NA](https://files.mtstatic.com/site_11811/78022/0?Expires=1777355777&Signature=KPfZvm6amQKnUx7tulJ4spbW4AmFbNQB366RYK86OlztC8BPQG-SihzkARVvhGFqXkqvZqmhsyClWPx15K9kC5FucxRfuOr6cJCTEyYLdaSjohXh9~lnChTleDhKj9efOLp2aO9hFz-WGNbOAkylsRaM2yQSDb4YZzN3UNjnYoA_&Key-Pair-Id=APKAJ5Y6AV4GI7A555NA)  
15. Fulfillment Configuration | Unified Library Management System Guide, accessed on May 18, 2026, [https://ulmsguide.calstate.edu/ulms-guide/resource-sharing/configuration/alma-peer-peer-resource-sharing/fulfillment-configuration](https://ulmsguide.calstate.edu/ulms-guide/resource-sharing/configuration/alma-peer-peer-resource-sharing/fulfillment-configuration)  
16. Configuring Peer to Pe... \- Alma Documentation, accessed on May 18, 2026, [https://alma.wrlc.org/books/fulfillment/page/configuring-peer-to-peer-resource-sharing-in-the-iz](https://alma.wrlc.org/books/fulfillment/page/configuring-peer-to-peer-resource-sharing-in-the-iz)  
17. kurtmunson/ILLiad-NCIP: ILLiad Alma NCIP Addon \- GitHub, accessed on May 18, 2026, [https://github.com/kurtmunson/ILLiad-NCIP](https://github.com/kurtmunson/ILLiad-NCIP)  
18. Alma 2023 Release Notes \- Ex Libris Knowledge Center, accessed on May 18, 2026, [https://knowledge.exlibrisgroup.com/Alma/Release\_Notes/2023/Alma\_2023\_Release\_Notes](https://knowledge.exlibrisgroup.com/Alma/Release_Notes/2023/Alma_2023_Release_Notes)  
19. Possible actions for libraries to consider in resource sharing, accessed on May 18, 2026, [https://lib.haifa.ac.il/wp-content/uploads/2025/08/Possible\_Resource\_Sharing\_actions\_during\_a\_crisis.pdf](https://lib.haifa.ac.il/wp-content/uploads/2025/08/Possible_Resource_Sharing_actions_during_a_crisis.pdf)