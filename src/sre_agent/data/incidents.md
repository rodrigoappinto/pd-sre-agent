# Incident ANON-DB-POOL-001

## Scope
global

## Tenant
anonymized

## Service
api-service

## Summary
An API returned elevated 5xx responses because a database connection pool was exhausted by a scheduled reconciliation job.

## Resolution
Pause the reconciliation job, then verify database connection availability and 5xx responses return to baseline.
