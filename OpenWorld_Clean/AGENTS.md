# Instructions for this reduced learning copy

Read `README.md` first. This is a selected subset of `../OpenWorld-main`,
not a complete checkout of its research project. Do not reintroduce the full
repository, benchmarks, or research scaffolding during routine maintenance.

- Preserve runtime behavior unless the owner requests a code change.
- Keep normative documentation and code comments in English. Vietnamese
  explanatory onboarding may live in `docs/vi/`, with a source link and date.
- Distinguish simulated feedback and inferred predictions from real evidence.
- Preserve event provenance, permission checks, owner boundaries, and replay.
- Do not call paid APIs or access secrets without task authorization.
- Keep the original project and the Gemini extension outside this copy's edits
  unless the task explicitly concerns them.
- Validate relevant changes locally with the demo and retained integration
  tests. Do not present their results as validation of the full project.

Commands from this directory:

```console
python -B examples/r0_agent_cycle.py
python -B -m unittest discover -s tests -v
```
