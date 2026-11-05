.PHONY: mock-up mock-down mcp-up mcp-down check test mcp-smoke

mock-up:
	docker compose -f mock-slack/compose.yml up -d --build --wait
mock-down:
	docker compose -f mock-slack/compose.yml down
mcp-up:
	docker compose -f mcp/compose.yml up -d --build
mcp-down:
	docker compose -f mcp/compose.yml down
check:
	npm --prefix mock-slack run check
	python -m py_compile mcp/smoke.py
test:
	npm --prefix mock-slack test
mcp-smoke:
	docker compose -f mcp/compose.yml exec -T postgres-mcp python - < mcp/smoke.py
