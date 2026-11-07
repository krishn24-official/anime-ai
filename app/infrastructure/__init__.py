"""Infrastructure layer: implementations of domain ports (MongoDB, Cloudinary, ...).

This is the only layer that may talk to databases and external SDKs. To change the
database, write new implementations of the domain ports here and wire them in
app/container.py; domain and application code stay unchanged.
"""
