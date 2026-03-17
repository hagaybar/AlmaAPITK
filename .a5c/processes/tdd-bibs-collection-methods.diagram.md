# TDD Process Flow Diagram

```
+------------------+
|  START           |
+--------+---------+
         |
         v
+------------------+     +-------------------+
| Phase 1: RED     |---->| Write Integration |
| (Write Tests)    |     | Tests First       |
+--------+---------+     +-------------------+
         |                        |
         v                        v
+------------------+     +-------------------+
| Run Tests        |---->| Tests FAIL        |
| (Expect Failure) |     | (Expected)        |
+--------+---------+     +-------------------+
         |
         v
+------------------+     +-------------------+
| Phase 2: GREEN   |---->| Implement         |
| (Implementation) |     | Methods           |
+--------+---------+     +-------------------+
         |                        |
         v                        v
+------------------+     +-------------------+
| Run Tests        |---->| Tests PASS        |
| (Expect Pass)    |     |                   |
+--------+---------+     +-------------------+
         |
         v
+------------------+     +-------------------+
| Phase 3: REFACTOR|---->| Code Quality      |
|                  |     | Check             |
+--------+---------+     +-------------------+
         |
         v
+------------------+
| BREAKPOINT       |
| (Optional: SB    |
|  Collection ID)  |
+--------+---------+
         |
         v
+------------------+     +-------------------+
| Final            |---->| Smoke Test        |
| Verification     |     | + Summary         |
+--------+---------+     +-------------------+
         |
         v
+------------------+
|  COMPLETE        |
+------------------+
```

## Tasks Summary

| Phase | Task | Kind | Description |
|-------|------|------|-------------|
| 1 | write-integration-tests | agent | Create test file with all test cases |
| 1 | run-pytest | shell | Run tests (expect failures) |
| 2 | implement-methods | agent | Add methods to bibs.py |
| 2 | run-pytest | shell | Run tests (expect pass) |
| 3 | code-quality-check | agent | Review and fix quality issues |
| 3 | breakpoint | breakpoint | Optional sandbox collection ID |
| 3 | final-verification | agent | Smoke test and summary |
