"""SCL-3 scenarios for `make bench`: list, filter and search as an analyst and as a senior reviewer."""

BENCHMARKS = [
    ("list (senior, all countries)", "TEST-USR-CAMILA", "/kyc/cases?page=1&page_size=50"),
    ("list (analyst, MX+CO)", "TEST-USR-ANA", "/kyc/cases?page=1&page_size=50"),
    (
        "queue default (open, oldest first)",
        "TEST-USR-ANA",
        "/kyc/cases?status=new,in_review,recommended&sort=created_at&order=asc",
    ),
    ("list page 500", "TEST-USR-CAMILA", "/kyc/cases?page=500&page_size=50"),
    ("filter status=new&country=MX", "TEST-USR-ANA", "/kyc/cases?status=new&country=MX"),
    ("filter risk=high&screening=match", "TEST-USR-CAMILA", "/kyc/cases?risk=high&screening_result=match"),
    ("filter sort=reference desc", "TEST-USR-CAMILA", "/kyc/cases?sort=reference&order=desc"),
    ("search reference prefix", "TEST-USR-CAMILA", "/kyc/cases?q=TEST-KYC-0123"),
    ("search digits", "TEST-USR-ANA", "/kyc/cases?q=4521"),
    ("count filtered", "TEST-USR-ANA", "/kyc/cases/count?status=new"),
]
