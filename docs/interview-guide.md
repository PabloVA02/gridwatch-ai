# Interview preparation guide

This document is for the author before presenting GridWatch AI in an interview. Do not memorise
phrases: run the application and verify each claim yourself.

## 60-second explanation

GridWatch AI receives batches of energy telemetry, validates and stores them, and then uses an
Isolation Forest to find readings that differ from the behaviour of a selected device and time
window. It combines energy, voltage, temperature, sudden consumption change and cyclical time
features. The API ranks anomalies and adds a simple statistical explanation. I made the result
reproducible with a fixed seed and a SHA-256 input/configuration fingerprint. Each execution records
its detector and feature-schema versions. A separate monitoring endpoint compares reference and
current windows with PSI and reports slot-based time-series completeness and boundary/internal
gaps. It requires 300 values per window because smaller samples made PSI too noisy in simulation.
All timestamps are timezone-aware and normalized to UTC before duplicate checks. I tested the complete
flows, versioned the schema with Alembic and packaged it with Docker and PostgreSQL.

## Questions you must be ready to answer

1. **Why Isolation Forest?** It works without labelled failures and isolates rare points efficiently.
   Its output is anomaly evidence, not a diagnosis.
2. **Why cyclical sine/cosine time features?** Hour 23 and hour 0 are neighbours; raw hour numbers
   would incorrectly make them appear far apart.
3. **Why a unique device/timestamp constraint?** It prevents accidental duplicate telemetry at the
   database boundary, including concurrent requests.
4. **Why a fixed random seed?** Repeated tests and demos should produce the same result.
5. **What would change at scale?** Queue ingestion, time partitioning, bulk inserts, asynchronous
   processing, model registry, observability and drift monitoring.
6. **What is the main risk?** False positives and treating correlation as causation. Operators must
   review alerts and the system should learn from labelled outcomes.
7. **What does the fingerprint prove?** It proves that the canonical data values and detector
   configuration supplied to two runs are identical. It does not prove model quality or replace
   access controls and lineage for upstream raw data.
8. **Why PSI, and why 300 samples?** PSI is a simple, explainable comparison of distribution
   proportions that works without labels. Here the reference defines five quantile buckets with a
   0.5 pseudocount. Small samples produced many false warnings; at 300 points, a seeded 2,000-pair
   same-normal-distribution check produced approximately a 0.4% warning rate and no drift alerts.
   That controlled check supports the floor but real thresholds still need calibration per device
   and season.
9. **Why monitor completeness separately?** Missing samples can distort feature distributions and
   create false drift. I count occupied expected-time slots and leading/internal/trailing missing
   slots, rather than just rows, so a concentrated burst cannot look like full-window coverage.
10. **Is this a full model registry?** No. It is a lightweight database audit of runs and input
    identity. If trained artefacts were reused and promoted, I would add artefact storage, approval
    stages and a tool such as MLflow.

## Hands-on checklist

- Start the local API and open `/docs`.
- Generate the demo payload and ingest it.
- Explain every field in `AnalysisRequest`.
- Change contamination from `0.08` to `0.20` and observe the effect.
- Run the tests and read at least one API test and the detector test.
- Repeat an analysis and verify that `run_id` changes while `dataset_fingerprint` remains stable.
- Compare two windows through `/api/v1/monitoring/drift`, then remove one sample and inspect the gap.
- Explain why PSI signals a change but cannot diagnose its cause.
- Explain why naive timestamps are rejected and demonstrate two offset representations of the same
  instant producing a duplicate conflict after UTC normalization.
- Locate the unique constraint and Alembic migration.
- Draw the architecture without looking at the README.
