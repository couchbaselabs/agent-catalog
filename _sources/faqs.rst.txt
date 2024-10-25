.. role:: python(code)
   :language: python

Frequently Asked Questions
==========================

This section provides answers to common questions about the project. It covers key concepts, solutions to typical issues,
and guidance on using various features. For additional information, consult the documentation or community resources.

How to roll back to a previous catalog version?
-----------------------------------------------

After publishing multiple versions of your tool or prompt catalog, each with its own set of use cases, you may want to
test each version individually and have the option to roll back to a previous catalog version.

Catalog versions are nothing but git commit hashes and can published catalogs (residing in Couchbase) can be tracked
with their ``catalog id``. Following is a step by step guide to do the same.

1. **List catalog versions** : Start by running the ``agentc status`` command with the following options to list all the
published catalog versions of tools in your bucket (here, we are checking in ``travel-sample``):

.. code-block:: bash

    # run agentc status --help for all options
    agentc status --kind tool --status-db --bucket travel-sample

This will return a list of all the catalogs you have published so far as shown below.

.. code-block:: console
    :emphasize-lines: 5, 16

    -----------------------------------------------------------------
    TOOL
    -----------------------------------------------------------------
    db catalog info:
        catalog id: 53010a92d74e96851fb36fc2c69b9c3337140890
                path            : travel-sample.agent_catalog.tool
                schema version  : 0.0.0
                kind of catalog : tool
                repo version    :
                        time of publish: 2024-10-23 07:16:15.058405+00:00
                        catalog identifier: 53010a92d74e96851fb36fc2c69b9c3337140890
                embedding model : sentence-transformers/all-MiniLM-L12-v2
                source dirs     : ['src/resources/agent_c/tools']
                number of items : 24

        catalog id: fe25a5755bfa9af68e1f1fae9ac45e9e37b37611
                path            : travel-sample.agent_catalog.tool
                schema version  : 0.0.0
                kind of catalog : tool
                repo version    :
                        time of publish: 2024-10-16 05:34:38.523755+00:00
                        catalog identifier: fe25a5755bfa9af68e1f1fae9ac45e9e37b37611
                embedding model : sentence-transformers/all-MiniLM-L12-v2
                source dirs     : ['src/resources/tools']
                number of items : 2

    -----------------------------------------------------------------

2. **Browse git commits**: Next, check the ``catalog id`` from the above output for the git commit hash at which the
catalogs were published to the database. Open your repository commit history on github or run :command:`git log` in
your terminal to view the commit history for your project and choose a commit to roll back to.

4. On deciding the catalog version to roll back to, use the following git command(s) to:

a. Revert changes to a particular commit - :command:`git revert <commit_hash>..HEAD` will change commit history and
revert all commits till the specified one.

b. Checkout to a particular commit - :command:`git checkout <commit_hash>` will checkout to a published commit but will
not push any changes

c. Remove unpublished changes - :command:`git reset --hard <commit_hash>` will reset HEAD to the provided commit if
you have not published your changes so far

`Apart from these commands, please refer to git documentation for more information on reverting or rolling back.`


With this, you will have rolled back to your desired catalog version. Make sure to have committed (and published) your
current local catalog to avoid losing track!
