# Newer versions of the rosetta core library / tools might be
# able to read and/or write older catalog schema versions of data
# which were persisted into the local catalog and/or into the database.
#
# If there's an incompatible catalog schema enhancement
# as part of the development of a next, upcoming release,
# the latest CATALOG_SCHEMA_VERSION should be bumped
# before the release.
CATALOG_SCHEMA_VERSION = "0.0.0"
