# Interview preparation guide

This document is for the author before presenting GridWatch AI in an interview. Do not memorise
phrases: run the application and verify each claim yourself.

## 60-second explanation

GridWatch AI receives batches of energy telemetry, validates and stores them, and then uses an
Isolation Forest to find readings that differ from the behaviour of a selected device and time
window. It combines energy, voltage, temperature, sudden consumption change and cyclical time
features. The API ranks anomalies and adds a simple statistical explanation. I made the result
reproducible with a fixed seed, tested the complete ingestion-to-analysis flow, versioned the schema
with Alembic and packaged it with Docker and PostgreSQL.

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

## Hands-on checklist

- Start the local API and open `/docs`.
- Generate the demo payload and ingest it.
- Explain every field in `AnalysisRequest`.
- Change contamination from `0.08` to `0.20` and observe the effect.
- Run the tests and read at least one API test and the detector test.
- Locate the unique constraint and Alembic migration.
- Draw the architecture without looking at the README.
