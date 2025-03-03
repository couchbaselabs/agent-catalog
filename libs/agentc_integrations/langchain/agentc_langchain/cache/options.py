import couchbase.auth
import couchbase.cluster
import couchbase.options
import datetime
import pathlib
import pydantic
import pydantic_settings
import typing

from agentc_core.config import RemoteCatalogConfig
from agentc_langchain.defaults import DEFAULT_COUCHBASE_CACHE_COLLECTION_NAME
from agentc_langchain.defaults import DEFAULT_COUCHBASE_CACHE_INDEX_NAME
from agentc_langchain.defaults import DEFAULT_COUCHBASE_CACHE_INDEX_SCORE_THRESHOLD
from agentc_langchain.defaults import DEFAULT_COUCHBASE_CACHE_SCOPE_NAME


class CacheOptions(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(env_prefix="AGENT_CATALOG_LANGCHAIN_CACHE_")

    # Connection-specific details.
    conn_string: typing.Optional[str] = None
    """ The connection string to the Couchbase cluster hosting the cache.

    This field **must** be specified.
    """

    username: typing.Optional[str] = None
    """ Username associated with the Couchbase instance hosting the cache.

    This field **must** be specified.
    """

    password: typing.Optional[pydantic.SecretStr] = None
    """ Password associated with the Couchbase instance hosting the cache.

    This field **must** be specified.
    """

    conn_root_certificate: typing.Optional[str | pathlib.Path] = None
    """ Path to the root certificate file for the Couchbase cluster.

    This field is optional and only required if the Couchbase cluster is using a self-signed certificate.
    """

    # Collection-specific details.
    bucket: typing.Optional[str] = None
    """ The name of the Couchbase bucket hosting the cache.

    This field **must** be specified.
    """

    scope: typing.Optional[str] = pydantic.Field(default=DEFAULT_COUCHBASE_CACHE_SCOPE_NAME)
    """ The name of the Couchbase scope hosting the cache.

    This field is optional and defaults to :py:data:`agentc_langchain.defaults.DEFAULT_COUCHBASE_CACHE_SCOPE_NAME`.
    """

    collection: typing.Optional[str] = pydantic.Field(default=DEFAULT_COUCHBASE_CACHE_COLLECTION_NAME)
    """ The name of the Couchbase collection hosting the cache.

    This field is optional and defaults to :py:data:`agentc_langchain.defaults.DEFAULT_COUCHBASE_CACHE_COLLECTION_NAME`.
    """

    index_name: typing.Optional[str] = pydantic.Field(default=DEFAULT_COUCHBASE_CACHE_INDEX_NAME)
    """ The name of the Couchbase FTS index used to query the cache.

    This field will only be used if the cache is of type `semantic`.
    If the cache is of type `semantic` and this field is not specified, this field defaults to
    :py:data:`agentc_langchain.defaults.DEFAULT_COUCHBASE_CACHE_INDEX_NAME`.
    """

    ttl: typing.Optional[datetime.timedelta] = None
    """ The time-to-live (TTL) for the cache.

    When specified, the cached documents will be automatically removed after the specified duration.
    This field is optional and defaults to None.
    """

    score_threshold: typing.Optional[float] = pydantic.Field(default=DEFAULT_COUCHBASE_CACHE_INDEX_SCORE_THRESHOLD)
    """ The score threshold used to quantify what constitutes as a "good" match.

    This field will only be used if the cache is of type `semantic`.
    If the cache is of type `semantic` and this field is not specified, this field defaults to
    :py:data:`agentc_langchain.defaults.DEFAULT_COUCHBASE_CACHE_INDEX_SCORE_THRESHOLD`.
    """

    @pydantic.model_validator(mode="after")
    def _pull_cluster_from_agent_catalog(self) -> typing.Self:
        config = RemoteCatalogConfig()
        if self.conn_string is None:
            self.conn_string = config.conn_string
        if self.username is None:
            self.username = config.username
        if self.password is None:
            self.password = config.password
        if self.conn_root_certificate:
            self.conn_root_certificate = config.conn_root_certificate
        if self.bucket is None:
            self.bucket = config.bucket
        return self

    def Cluster(self) -> couchbase.cluster.Cluster:
        if self.conn_root_certificate is not None and isinstance(self.conn_root_certificate, pathlib.Path):
            conn_root_certificate = self.conn_root_certificate.absolute()
        else:
            conn_root_certificate = self.conn_root_certificate

        return couchbase.cluster.Cluster(
            self.conn_string,
            couchbase.options.ClusterOptions(
                couchbase.auth.PasswordAuthenticator(
                    username=self.username,
                    password=self.password.get_secret_value(),
                    cert_path=conn_root_certificate,
                )
            ),
        )
