# Development rules

- Start each new feature on a dedicated development branch. Do not develop on
  `main`. Merge back only after the user confirms the feature is final.
- Use the user's disposable clean Windows environment proactively when native
  Windows or frozen-executable verification is needed. Follow the local
  `win10-vm` skill, retrieve evidence, and clean up the task's VM and tunnel.
- Preserve pinned dependencies, ephemeris data, historical numerical archives,
  and personal databases. Use isolated synthetic data for tests.
- Keep hardware and multiprocessing implementation details out of ordinary user
  workflows. Progress must describe actual work, support cancellation, and never
  invent an ETA before measurements are available.
