"""Application layer: use cases.

Depends only on app.domain. Must not import FastAPI, pymongo/bson, app.infrastructure,
or the legacy app.api / app.repositories / app.db packages.
Enforced by tests/test_architecture.py.
"""
