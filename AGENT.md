# Travel Coding Agent Instructions (Codex cloud + GitHub + Vercel)

## Operating rules
- Always work in a new branch and open a PR to the default branch (main/master). Never commit directly to the default branch.
- Keep diffs minimal. Do not refactor unrelated code.
- If you need env vars, use `.env.example` and safe mocks. Do not require production secrets to run.
- Prefer incremental delivery: plan first, then implement.
- If tests fail twice, stop and summarize root cause and next actions.

## Required workflow
1) Restate the goal in 1 sentence.
2) Output a short plan: steps and exact files you will touch.
3) Wait for my "GO" before coding.
4) Implement.
5) Run checks:
   - If repo has npm scripts: run `npm run check` or run lint + typecheck + tests.
   - Otherwise run the closest available test or lint commands listed in README or package.json.
6) Open a PR:
   - PR title: concise
   - PR description: what changed + how to test + screenshots if UI
7) After PR is created, tell me:
   - PR link
   - Which URL path to open on the Vercel Preview to verify

## Default prompt format I will use
Task:
- Goal:
- User story:
- Acceptance criteria: (1) (2) (3)

Constraints:
- (optional list)

Deliverable:
- PR + Vercel preview verification steps
