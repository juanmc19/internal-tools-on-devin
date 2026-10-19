"""`make bench` scenarios for the Refunds Desk: list, filter and search as an agent and as an approver."""

BENCHMARKS = [
    ("list (approver, all regions)", "TEST-USR-INES", "/refunds?page=1&page_size=50"),
    ("list (agent, NE+SE)", "TEST-USR-GABRIELA", "/refunds?page=1&page_size=50"),
    (
        "queue default (open, oldest first)",
        "TEST-USR-GABRIELA",
        "/refunds?status=requested,pending_second_approval&sort=created_at&order=asc",
    ),
    ("filter type=dispute&region=west", "TEST-USR-INES", "/refunds?type=dispute&region=west"),
    ("filter sort=amount desc", "TEST-USR-INES", "/refunds?sort=amount_cents&order=desc"),
    (
        "queue by Reg E deadline (most urgent first)",
        "TEST-USR-INES",
        "/refunds?status=requested,pending_second_approval&sort=deadline_on&order=asc",
    ),
    ("search reference prefix", "TEST-USR-INES", "/refunds?q=TEST-RFD-0123"),
    ("count filtered", "TEST-USR-GABRIELA", "/refunds/count?status=requested"),
]
