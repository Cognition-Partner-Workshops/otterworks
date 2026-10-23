# PR CI only: literal ids so the plan makes no AWS calls. None of these exist.
offline_plan        = true
vpc_id              = "vpc-0123456789abcdef0"
subnet_ids          = ["subnet-0123456789abcdef0", "subnet-0fedcba9876543210"]
allowed_cidr_blocks = ["10.0.0.0/16"]
