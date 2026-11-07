"""In-memory implementations of domain ports, for fast unit tests without a database.

They double as proof that the use cases do not depend on MongoDB: any storage that
implements the port works.
"""
