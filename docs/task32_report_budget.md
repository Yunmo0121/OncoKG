# EXP-T32-01 · Configurable report budget

The renderer accepts a positive integer budget and defaults to three.
On SYN-32, budgets 2, 3 and 4 retained 0, 1 and 1 review flags.
Only budget 4 included the eligibility source and both sourced conflict checks.

```bash
PYTHONPATH=codes/demo python -m unittest test_task32_report_budget -v
```
