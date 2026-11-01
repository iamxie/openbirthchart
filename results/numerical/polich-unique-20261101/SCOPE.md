# Authorized scope — 2026-11-01

- Only Polich–Page (T): require unique, continuous geometrical placement before accepting a chart.
- Check the continuous ecliptic cusp family as well as each actual/zero-latitude input point. Reject the entire chart for a folded/degenerate family or a non-unique/degenerate individual placement.
- Preserve valid raw LibEphemeris house_pos values; do not repair LibEphemeris. A cusp correction requires geometric identity, uniqueness/continuity and a demonstrably small numerical residual. Remove unconditional T ASC identity overrides.
- Retain existing five interleaved-cusp refusals. Other systems, including Koch's undefined sentinel policy, are outside this T-specific change.
- Preserve fixed inputs, baseline contents/current pointers, dependencies, ephemerides, personal data and existing EXE/ZIP. Save candidate captures and complete impact analysis separately.
- Write paired Traditional Chinese/English articles about (2) justified cusp residual correction, (3) non-continuous geometry, (4) ambiguous individual bodies; also finish the pending Azimuth explanation article. Existing docs directory and bilingual Markdown convention apply.
- Leap-second input and generic GitHub reporting TODOs are not authorized by this request to finish articles.
- Validate focused geometry tests, full desktop tests, all three current regression suites in both latitude modes, refusal translations and prevention of exporting stale results.

Design: a separate application module validates the unchanged library's circle family using plane equations. It enumerates all stationary intervals analytically, counts distinct oriented roots (not antipodal duplicates), and rejects uncertainty/degeneracy instead of selecting an arbitrary root. Independent mathematical checks and synthetic controls supplement archived cases; raw output, rejection reasons and numerical tolerances remain auditable.

Neighborhood validation additionally reproduced unique non-cusp points whose library residual crosses a numbered boundary (e.g. normal 1904-11 cusp 2 minus 1e-6 degrees). The authorized identity-only correction rule forbids snapping these points. The implementation therefore refuses a raw house that contradicts the independent unique root, or a boundary side that cannot be numerically distinguished, using a separate precision/boundary message rather than falsely calling it geometric multiplicity. Initial captures remain in captures/; final captures including this guard are in captures-final/.
